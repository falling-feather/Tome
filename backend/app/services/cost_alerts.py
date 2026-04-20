"""v2.20: 费用告警 Webhook 推送。

使用场景：
- /api/admin/health 返回 cost_alerts 时，若有任一 key 处于 "breached"，
  通过 maybe_send_alerts() 异步推送到 LLM_ALERT_WEBHOOK_URL；
- 同一 key 在 LLM_ALERT_WEBHOOK_COOLDOWN_SEC 内不会重复推送（防风暴）；
- 推送失败仅写日志，不影响主流程。

负载格式：
{
  "type": "cost_alert",
  "key": "daily" | "monthly",
  "level": "breached",
  "used_usd": 12.34,
  "limit_usd": 10.0,
  "ratio": 1.234,
  "ts": "2026-04-20T05:30:00Z"
}
"""
from __future__ import annotations

import logging
import time
from typing import Optional

import httpx

from backend.app.config import settings

logger = logging.getLogger(__name__)

# 模块级 in-memory state — 单进程足够；多进程部署时建议用 Redis 替代
_last_sent: dict[str, float] = {}


def _should_send(key: str, cooldown: int) -> bool:
    now = time.time()
    last = _last_sent.get(key, 0.0)
    if now - last < cooldown:
        return False
    return True


def _mark_sent(key: str) -> None:
    _last_sent[key] = time.time()


def reset_state() -> None:
    """测试用：清空冷却状态。"""
    _last_sent.clear()


async def _post(url: str, payload: dict, timeout: float = 5.0) -> bool:
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.post(url, json=payload)
            r.raise_for_status()
            return True
    except Exception as e:  # noqa: BLE001
        logger.warning("cost alert webhook failed url=%s err=%s", url, e)
        return False


async def maybe_send_alerts(
    cost_alerts: Optional[dict],
    *,
    url: Optional[str] = None,
    cooldown: Optional[int] = None,
    poster=None,
) -> list[str]:
    """检查 cost_alerts，若有 breached key 则推送 webhook。

    返回本次实际推送的 key 列表（用于日志/测试断言）。
    `poster` 参数用于测试注入；默认使用 _post。
    """
    if not cost_alerts:
        return []
    target_url = url if url is not None else settings.LLM_ALERT_WEBHOOK_URL
    if not target_url:
        return []
    cd = cooldown if cooldown is not None else int(settings.LLM_ALERT_WEBHOOK_COOLDOWN_SEC)
    send = poster if poster is not None else _post

    sent: list[str] = []
    import datetime as _dt

    for key in ("daily", "monthly"):
        block = cost_alerts.get(key) or {}
        if block.get("level") != "breached":
            continue
        if not _should_send(key, cd):
            continue
        payload = {
            "type": "cost_alert",
            "key": key,
            "level": "breached",
            "used_usd": block.get("used_usd"),
            "limit_usd": block.get("limit_usd"),
            "ratio": block.get("ratio"),
            "ts": _dt.datetime.utcnow().isoformat() + "Z",
        }
        ok = await send(target_url, payload)
        if ok:
            _mark_sent(key)
            sent.append(key)
    return sent
