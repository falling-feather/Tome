import httpx
import json
import time
import logging
from typing import AsyncGenerator, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.app.config import settings
from backend.app.models import UserApiKey
from backend.app.services.prompt_assembler import PromptAssembler
from backend.app.services.world_book import WorldBookService
from backend.app.services.memory_service import MemoryService
from backend.app.tracing import traced_span
from backend.app.services.cost import record_usage as _record_llm_usage

logger = logging.getLogger("inkless")
from backend.app.services.resilience import (
    llm_circuit_breaker, llm_fallback_circuit_breaker, health_metrics,
)

# ---------------------------------------------------------------------------
# 模块级共享 httpx.AsyncClient（连接复用）
# ---------------------------------------------------------------------------
_shared_client: httpx.AsyncClient | None = None


def _get_shared_client() -> httpx.AsyncClient:
    global _shared_client
    if _shared_client is None or _shared_client.is_closed:
        _shared_client = httpx.AsyncClient(
            timeout=httpx.Timeout(60.0, connect=10.0),
            limits=httpx.Limits(max_connections=50, max_keepalive_connections=20),
        )
    return _shared_client


class LLMService:
    def __init__(self, user_id: int = 0, db: Optional[AsyncSession] = None):
        self.user_id = user_id
        self.db = db
        self.deepseek_key = settings.DEEPSEEK_API_KEY
        self.deepseek_url = settings.DEEPSEEK_BASE_URL
        self.deepseek_model = settings.DEEPSEEK_MODEL
        self.siliconflow_key = settings.SILICONFLOW_API_KEY
        self.siliconflow_url = settings.SILICONFLOW_BASE_URL
        self.siliconflow_model = settings.SILICONFLOW_MODEL

    async def load_user_keys(self):
        if not self.db or not self.user_id:
            return
        result = await self.db.execute(
            select(UserApiKey).where(UserApiKey.user_id == self.user_id)
        )
        for key in result.scalars().all():
            if key.provider == "deepseek" and key.api_key:
                self.deepseek_key = key.api_key
                if key.base_url:
                    self.deepseek_url = key.base_url
                if key.model:
                    self.deepseek_model = key.model
            elif key.provider == "siliconflow" and key.api_key:
                self.siliconflow_key = key.api_key
                if key.base_url:
                    self.siliconflow_url = key.base_url
                if key.model:
                    self.siliconflow_model = key.model

    def _get_provider(self) -> tuple[str, str, str]:
        """Return (api_key, base_url, model) - DeepSeek priority."""
        if self.deepseek_key:
            return self.deepseek_key, self.deepseek_url, self.deepseek_model
        if self.siliconflow_key:
            return self.siliconflow_key, self.siliconflow_url, self.siliconflow_model
        raise ValueError("没有可用的 API Key，请在设置中配置")

    def _get_fallback_provider(self) -> tuple[str, str, str] | None:
        """Return fallback provider if primary is DeepSeek and SiliconFlow is available."""
        if self.deepseek_key and self.siliconflow_key:
            return self.siliconflow_key, self.siliconflow_url, self.siliconflow_model
        return None

    def _build_system_prompt(self, state: dict) -> str:
        """Fallback prompt builder — used only when assembler is unavailable."""
        char_name = state.get("character_name", "旅行者")
        char_class = state.get("character_class", "冒险者")
        location = state.get("current_location", "未知之地")
        hp = state.get("health", 100)
        max_hp = state.get("max_health", 100)
        gold = state.get("money", 50)
        fatigue = state.get("fatigue", 0)
        status = state.get("status", "exploring")
        chapter = state.get("chapter", 1)
        turn = state.get("turn", 0)
        inventory = state.get("inventory", [])
        quest_flags = state.get("quest_flags", {})

        status_names = {
            "exploring": "探索中", "combat": "战斗中", "resting": "休息中",
            "trading": "交易中", "dialogue": "对话中", "dead": "已死亡",
        }
        inv_str = "、".join(inventory[:10]) if inventory else "无"
        quest_str = "、".join(quest_flags.keys()) if quest_flags else "无"
        hp_pct = hp / max_hp * 100 if max_hp > 0 else 100
        health_desc = "状态良好" if hp_pct > 80 else "有些伤痕" if hp_pct > 50 else "伤势不轻" if hp_pct > 25 else "奄奄一息"
        fatigue_desc = "精力充沛" if fatigue < 30 else "有些疲惫" if fatigue < 60 else "非常疲倦" if fatigue < 85 else "筋疲力尽"

        return (
            f"你是一个互动文字冒险游戏的叙事引擎。\n"
            f"## 当前世界状态\n"
            f"- 玩家角色：{char_name}（{char_class}）\n- 位置：{location}\n"
            f"- 状态：{status_names.get(status, '探索中')}\n"
            f"- HP：{hp}/{max_hp}（{health_desc}） 疲劳：{fatigue}/100（{fatigue_desc}）\n"
            f"- 金币：{gold} 背包：{inv_str}\n- 任务：{quest_str}\n"
            f"- 回合{turn} · 第{chapter}章\n"
            f"## 规则\n以第二人称叙事，200-400字，暗示数值变化。"
        )

    async def build_system_prompt(self, state: dict, event_context: str = "", user_action: str = "", session_id: str = "") -> str:
        """
        使用 PromptAssembler + WorldBook + MemoryService 构建 system prompt.
        如果数据库不可用则回退到简单模式.
        """
        if not self.db:
            prompt = self._build_system_prompt(state)
            if event_context:
                prompt += f"\n\n【当前触发事件】{event_context}"
            return prompt

        try:
            # 世界书检索
            wb = WorldBookService(self.db)
            scenario = state.get("scenario", "fantasy")
            chapter = state.get("chapter", 1)
            context_text = f"{user_action} {state.get('current_location', '')} {state.get('status', '')}"
            lore = await wb.retrieve(scenario, chapter, context_text, top_k=5)

            # 记忆上下文检索
            memory_context = ""
            if session_id:
                try:
                    memory_svc = MemoryService(session_id, self.db)
                    memory_context = await memory_svc.retrieve_context(max_chars=1500)
                except Exception as e:
                    logger.warning(f"记忆检索失败: {e}")

            # Prompt 装配
            assembler = PromptAssembler(self.db)
            prompt = await assembler.assemble(state, lore, event_context)

            # 追加记忆上下文
            if memory_context:
                prompt += f"\n\n{memory_context}"

            return prompt
        except Exception as e:
            logger.warning(f"Prompt装配失败，使用回退: {e}")
            prompt = self._build_system_prompt(state)
            if event_context:
                prompt += f"\n\n【当前触发事件】{event_context}"
            return prompt

    async def _call_stream(
        self, api_key: str, base_url: str, model: str, messages: list, **kwargs
    ) -> AsyncGenerator[str, None]:
        url = f"{base_url.rstrip('/')}/chat/completions"
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        payload = {
            "model": model,
            "messages": messages,
            "stream": True,
            "max_tokens": 1024,
            "temperature": 0.85,
            "top_p": 0.9,
        }

        # 输入字符数 / 估算输入 token (中文 ~1.5 char/token, 英文 ~4 char/token, 取均值 2.5)
        input_chars = sum(len(m.get("content", "")) for m in messages)
        input_tokens_est = max(1, input_chars // 3)
        provider_host = base_url.split("//")[-1].split("/")[0]

        with traced_span(
            "llm.stream",
            **{
                "llm.model": model,
                "llm.provider": provider_host,
                "llm.input_chars": input_chars,
                "llm.input_tokens_est": input_tokens_est,
            },
        ) as span:
            t0 = time.time()
            output_chars = 0
            try:
                async with _get_shared_client().stream(
                    "POST", url, json=payload, headers=headers, timeout=60.0
                ) as response:
                    if response.status_code != 200:
                        body = await response.aread()
                        raise ValueError(f"LLM API 错误 ({response.status_code}): {body.decode()[:200]}")

                    async for line in response.aiter_lines():
                        if not line.startswith("data: "):
                            continue
                        data_str = line[6:].strip()
                        if data_str == "[DONE]":
                            break
                        try:
                            data = json.loads(data_str)
                            delta = data.get("choices", [{}])[0].get("delta", {})
                            content = delta.get("content", "")
                            if content:
                                output_chars += len(content)
                                yield content
                        except json.JSONDecodeError:
                            continue
            finally:
                latency_ms = (time.time() - t0) * 1000
                output_tokens_est = max(0, output_chars // 3)
                health_metrics.inc("llm_input_chars", input_chars)
                health_metrics.inc("llm_output_chars", output_chars)
                health_metrics.inc("llm_tokens_est", input_tokens_est + output_tokens_est)
                _record_llm_usage(model, input_tokens_est, output_tokens_est)
                if span is not None:
                    try:
                        span.set_attribute("llm.output_chars", output_chars)
                        span.set_attribute("llm.output_tokens_est", output_tokens_est)
                        span.set_attribute("llm.latency_ms", round(latency_ms, 1))
                    except Exception:
                        pass

    async def stream_narrative(
        self, state: dict, history: list[dict], user_action: str, event_context: str = "", session_id: str = ""
    ) -> AsyncGenerator[str, None]:
        api_key, base_url, model = self._get_provider()

        with traced_span(
            "llm.build_system_prompt",
            session_id=session_id,
            history_len=len(history),
            scenario=str(state.get("scenario") or ""),
        ):
            system_prompt = await self.build_system_prompt(state, event_context, user_action, session_id)

        messages = [{"role": "system", "content": system_prompt}]

        # Add recent history (limit context)
        if history:
            for msg in history[-16:]:
                messages.append({"role": msg["role"], "content": msg["content"]})

        # Ensure the latest user action is included
        if not messages or messages[-1].get("content") != user_action:
            messages.append({"role": "user", "content": user_action})

        start_time = time.time()
        health_metrics.inc("llm_requests")

        # 主路径 + 断路器
        if llm_circuit_breaker.can_execute():
            try:
                async for chunk in self._call_stream(api_key, base_url, model, messages):
                    yield chunk
                llm_circuit_breaker.record_success()
                health_metrics.record_timing("llm_stream_ms", (time.time() - start_time) * 1000)
                return
            except (ValueError, Exception) as e:
                llm_circuit_breaker.record_failure()
                health_metrics.inc("llm_primary_failures")

        # 回退路径 + 断路器
        fallback = self._get_fallback_provider()
        if fallback and llm_fallback_circuit_breaker.can_execute():
            try:
                fb_key, fb_url, fb_model = fallback
                async for chunk in self._call_stream(fb_key, fb_url, fb_model, messages):
                    yield chunk
                llm_fallback_circuit_breaker.record_success()
                health_metrics.record_timing("llm_fallback_ms", (time.time() - start_time) * 1000)
                return
            except (ValueError, Exception):
                llm_fallback_circuit_breaker.record_failure()
                health_metrics.inc("llm_fallback_failures")

        health_metrics.inc("llm_total_failures")
        raise ValueError("所有 LLM 服务均不可用")

    async def simple_completion(self, prompt: str, max_tokens: int = 256) -> str:
        """Non-streaming completion for utility tasks."""
        providers = [self._get_provider()]
        fb = self._get_fallback_provider()
        if fb:
            providers.append(fb)

        last_err = None
        for attempt_idx, (api_key, base_url, model) in enumerate(providers):
            url = f"{base_url.rstrip('/')}/chat/completions"
            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
            payload = {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens,
                "temperature": 0.7,
            }
            provider_host = base_url.split("//")[-1].split("/")[0]
            with traced_span(
                "llm.completion",
                **{
                    "llm.model": model,
                    "llm.provider": provider_host,
                    "llm.attempt": attempt_idx,
                    "llm.input_chars": len(prompt),
                },
            ) as span:
                t0 = time.time()
                try:
                    client = _get_shared_client()
                    resp = await client.post(url, json=payload, headers=headers, timeout=30.0)
                    resp.raise_for_status()
                    data = resp.json()
                    text = data["choices"][0]["message"]["content"]
                    usage = data.get("usage") or {}
                    in_tok = int(usage.get("prompt_tokens") or (len(prompt) // 3))
                    out_tok = int(usage.get("completion_tokens") or (len(text) // 3))
                    health_metrics.inc("llm_input_chars", len(prompt))
                    health_metrics.inc("llm_output_chars", len(text))
                    health_metrics.inc("llm_tokens_est", in_tok + out_tok)
                    _record_llm_usage(model, in_tok, out_tok)
                    if span is not None:
                        try:
                            span.set_attribute("llm.output_chars", len(text))
                            span.set_attribute("llm.input_tokens", in_tok)
                            span.set_attribute("llm.output_tokens", out_tok)
                            span.set_attribute("llm.latency_ms", round((time.time() - t0) * 1000, 1))
                        except Exception:
                            pass
                    return text
                except Exception as e:
                    last_err = e
                    health_metrics.inc("llm_completion_failures")
                    if span is not None:
                        try:
                            span.set_attribute("llm.error", str(e)[:200])
                        except Exception:
                            pass
                    continue
        raise last_err
