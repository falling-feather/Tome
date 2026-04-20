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

# 待持久化的小时桶 (hour_iso, model) -> {requests, input_tokens, output_tokens, cost_usd}
_pending_hour: dict[tuple[str, str], dict[str, float]] = defaultdict(
    lambda: {"requests": 0, "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0}
)


def _hour_bucket_iso(now=None):
    import datetime as _dt
    now = now or _dt.datetime.utcnow()
    return now.replace(minute=0, second=0, microsecond=0).isoformat()


def record_usage(model: str, input_tokens: int, output_tokens: int) -> None:
    if not model:
        model = "unknown"
    bucket = _llm_usage[model]
    in_tok = max(0, int(input_tokens))
    out_tok = max(0, int(output_tokens))
    bucket["input_tokens"] += in_tok
    bucket["output_tokens"] += out_tok
    bucket["requests"] += 1

    # 同步累加到当前小时桶
    pricing = _resolve_pricing()
    price = _match_model(model, pricing)
    cost_usd = 0.0
    if price is not None:
        cost_usd = (in_tok / 1000.0) * price[0] + (out_tok / 1000.0) * price[1]
    hour_iso = _hour_bucket_iso()
    pb = _pending_hour[(hour_iso, model)]
    pb["requests"] += 1
    pb["input_tokens"] += in_tok
    pb["output_tokens"] += out_tok
    pb["cost_usd"] += cost_usd


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
    _pending_hour.clear()


async def flush_pending_to_db(db) -> int:
    """把内存中的小时桶累加到 DB 持久化表 llm_usage_hour，返回写入/更新行数。"""
    from sqlalchemy import select
    from backend.app.models import LlmUsageHour
    import datetime as _dt

    if not _pending_hour:
        return 0
    pending = dict(_pending_hour)
    _pending_hour.clear()

    n = 0
    for (hour_iso, model), delta in pending.items():
        try:
            hour_dt = _dt.datetime.fromisoformat(hour_iso)
        except Exception:
            continue
        stmt = select(LlmUsageHour).where(
            LlmUsageHour.hour_bucket == hour_dt,
            LlmUsageHour.model == model,
        )
        existing = (await db.execute(stmt)).scalar_one_or_none()
        if existing:
            existing.requests = (existing.requests or 0) + int(delta["requests"])
            existing.input_tokens = (existing.input_tokens or 0) + int(delta["input_tokens"])
            existing.output_tokens = (existing.output_tokens or 0) + int(delta["output_tokens"])
            existing.cost_usd = float(existing.cost_usd or 0.0) + float(delta["cost_usd"])
        else:
            db.add(LlmUsageHour(
                hour_bucket=hour_dt,
                model=model,
                requests=int(delta["requests"]),
                input_tokens=int(delta["input_tokens"]),
                output_tokens=int(delta["output_tokens"]),
                cost_usd=float(delta["cost_usd"]),
            ))
        n += 1
    await db.commit()
    return n


async def get_usage_trend(db, hours: int = 24) -> list[dict]:
    """聚合最近 N 小时的总用量与费用，按小时降序到升序排列。"""
    from sqlalchemy import select, func
    from backend.app.models import LlmUsageHour
    import datetime as _dt

    cutoff = _dt.datetime.utcnow().replace(minute=0, second=0, microsecond=0) - _dt.timedelta(hours=max(1, hours) - 1)
    stmt = (
        select(
            LlmUsageHour.hour_bucket,
            func.sum(LlmUsageHour.requests).label("requests"),
            func.sum(LlmUsageHour.input_tokens).label("input_tokens"),
            func.sum(LlmUsageHour.output_tokens).label("output_tokens"),
            func.sum(LlmUsageHour.cost_usd).label("cost_usd"),
        )
        .where(LlmUsageHour.hour_bucket >= cutoff)
        .group_by(LlmUsageHour.hour_bucket)
        .order_by(LlmUsageHour.hour_bucket.asc())
    )
    rows = (await db.execute(stmt)).all()
    return [
        {
            "hour": r.hour_bucket.isoformat(),
            "requests": int(r.requests or 0),
            "input_tokens": int(r.input_tokens or 0),
            "output_tokens": int(r.output_tokens or 0),
            "cost_usd": round(float(r.cost_usd or 0.0), 4),
        }
        for r in rows
    ]


async def get_cost_alerts(db) -> dict:
    """统计今日 (UTC) 与本月已花费 USD，对照 settings 阈值给出 banner 状态。"""
    from sqlalchemy import select, func
    from backend.app.models import LlmUsageHour
    import datetime as _dt

    now = _dt.datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    async def _sum(since):
        stmt = select(func.coalesce(func.sum(LlmUsageHour.cost_usd), 0.0)).where(
            LlmUsageHour.hour_bucket >= since
        )
        v = (await db.execute(stmt)).scalar()
        return float(v or 0.0)

    daily_used = await _sum(today_start)
    monthly_used = await _sum(month_start)

    daily_limit = float(settings.LLM_DAILY_USD_LIMIT or 0.0)
    monthly_limit = float(settings.LLM_MONTHLY_USD_LIMIT or 0.0)
    rate = float(settings.USD_TO_CNY)

    def _status(used, limit):
        if limit <= 0:
            return {
                "limit_usd": 0.0,
                "used_usd": round(used, 4),
                "used_cny": round(used * rate, 4),
                "ratio": 0.0,
                "level": "off",
                "remaining_usd": None,
            }
        ratio = used / limit if limit > 0 else 0.0
        level = "ok"
        if ratio >= 1.0:
            level = "breached"
        elif ratio >= 0.8:
            level = "warn"
        return {
            "limit_usd": round(limit, 4),
            "limit_cny": round(limit * rate, 4),
            "used_usd": round(used, 4),
            "used_cny": round(used * rate, 4),
            "ratio": round(ratio, 4),
            "level": level,
            "remaining_usd": round(max(0.0, limit - used), 4),
        }

    return {
        "daily": _status(daily_used, daily_limit),
        "monthly": _status(monthly_used, monthly_limit),
    }
