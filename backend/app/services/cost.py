"""Per-model LLM usage tracking + cost estimation (v2.11).

设计：
- 模块级 `_llm_usage`：dict[model_name, dict] 累加 input_tokens/output_tokens/requests
- `record_usage(model, input_tokens, output_tokens)` — llm_service 调用
- `DEFAULT_PRICING`：常见模型 USD per 1K tokens（input/output），可经 settings.LLM_PRICING_JSON 覆盖
- `compute_cost_report(usd_to_cny)` — 返回 [{model, input_tokens, output_tokens, cost_usd, cost_cny}, ...] + totals
"""
from __future__ import annotations

import json
import logging
from collections import defaultdict
from typing import Any

from backend.app.config import settings

logger = logging.getLogger("inkless.cost")

# USD per 1K tokens (input, output).
DEFAULT_PRICING: dict[str, tuple[float, float]] = {
    # OpenAI
    "gpt-4o": (0.005, 0.015),
    "gpt-4o-mini": (0.00015, 0.0006),
    "gpt-4-turbo": (0.01, 0.03),
    "gpt-3.5-turbo": (0.0005, 0.0015),
    # Anthropic
    "claude-3-5-sonnet": (0.003, 0.015),
    "claude-3-haiku": (0.00025, 0.00125),
    "claude-3-opus": (0.015, 0.075),
    # DeepSeek
    "deepseek-chat": (0.00027, 0.0011),
    "deepseek-reasoner": (0.00055, 0.00219),
    # Qwen
    "qwen-plus": (0.0004, 0.0012),
    "qwen-turbo": (0.0001, 0.0003),
    # Moonshot
    "moonshot-v1-8k": (0.0017, 0.0017),
    "moonshot-v1-32k": (0.0033, 0.0033),
}


_llm_usage: dict[str, dict[str, int]] = defaultdict(
    lambda: {"input_tokens": 0, "output_tokens": 0, "requests": 0}
)


def record_usage(model: str, input_tokens: int, output_tokens: int) -> None:
    if not model:
        model = "unknown"
    bucket = _llm_usage[model]
    bucket["input_tokens"] += max(0, int(input_tokens))
    bucket["output_tokens"] += max(0, int(output_tokens))
    bucket["requests"] += 1


def _resolve_pricing() -> dict[str, tuple[float, float]]:
    pricing = dict(DEFAULT_PRICING)
    raw = (settings.LLM_PRICING_JSON or "").strip()
    if raw:
        try:
            override = json.loads(raw)
            for k, v in (override or {}).items():
                if isinstance(v, (list, tuple)) and len(v) == 2:
                    pricing[k] = (float(v[0]), float(v[1]))
                elif isinstance(v, dict):
                    pricing[k] = (float(v.get("input", 0)), float(v.get("output", 0)))
        except Exception as e:
            logger.warning("LLM_PRICING_JSON 解析失败: %s", e)
    return pricing


def _match_model(model: str, pricing: dict[str, tuple[float, float]]) -> tuple[float, float] | None:
    if model in pricing:
        return pricing[model]
    # 后缀/前缀宽松匹配（处理 deepseek-chat-v2、gpt-4o-2024-11-20 等）
    # 长 key 优先，避免 "gpt-4o" 抢匹 "gpt-4o-mini"
    lower = model.lower()
    for key in sorted(pricing.keys(), key=len, reverse=True):
        if key in lower or lower.startswith(key):
            return pricing[key]
    return None


def compute_cost_report(usd_to_cny: float | None = None) -> dict[str, Any]:
    pricing = _resolve_pricing()
    rate = float(usd_to_cny if usd_to_cny is not None else settings.USD_TO_CNY)
    rows: list[dict[str, Any]] = []
    total_usd = 0.0
    total_in = 0
    total_out = 0
    for model, bucket in sorted(_llm_usage.items()):
        in_tok = bucket["input_tokens"]
        out_tok = bucket["output_tokens"]
        price = _match_model(model, pricing)
        if price is None:
            cost_usd = 0.0
            priced = False
        else:
            cost_usd = (in_tok / 1000.0) * price[0] + (out_tok / 1000.0) * price[1]
            priced = True
        total_usd += cost_usd
        total_in += in_tok
        total_out += out_tok
        rows.append({
            "model": model,
            "requests": bucket["requests"],
            "input_tokens": in_tok,
            "output_tokens": out_tok,
            "cost_usd": round(cost_usd, 4),
            "cost_cny": round(cost_usd * rate, 4),
            "priced": priced,
        })
    return {
        "models": rows,
        "total_input_tokens": total_in,
        "total_output_tokens": total_out,
        "total_cost_usd": round(total_usd, 4),
        "total_cost_cny": round(total_usd * rate, 4),
        "usd_to_cny": rate,
    }


def reset_usage() -> None:
    _llm_usage.clear()
