"""v2.20+: 费用告警 Webhook 推送与管理端配置。"""
import pytest
from fastapi import HTTPException

from backend.app.config import settings
from backend.app.routers.admin import get_cost_alert_settings, update_cost_alert_settings
from backend.app.models import User
from backend.app.services import cost_alerts


@pytest.fixture(autouse=True)
def _reset():
    cost_alerts.reset_state()
    yield
    cost_alerts.reset_state()


@pytest.mark.asyncio
async def test_breached_triggers_webhook():
    calls = []

    async def fake_post(url, payload):
        calls.append((url, payload))
        return True

    alerts = {
        "daily": {"level": "breached", "used_usd": 12.0, "limit_usd": 10.0, "ratio": 1.2},
        "monthly": {"level": "ok"},
    }
    sent = await cost_alerts.maybe_send_alerts(
        alerts, url="http://example.com/hook", cooldown=60, poster=fake_post,
    )
    assert sent == ["daily"]
    assert len(calls) == 1
    assert calls[0][0] == "http://example.com/hook"
    assert calls[0][1]["key"] == "daily"
    assert calls[0][1]["type"] == "cost_alert"


@pytest.mark.asyncio
async def test_cooldown_suppresses_repeat():
    calls = []

    async def fake_post(url, payload):
        calls.append(payload["key"])
        return True

    alerts = {"daily": {"level": "breached", "used_usd": 12.0, "limit_usd": 10.0, "ratio": 1.2}}
    await cost_alerts.maybe_send_alerts(alerts, url="http://x", cooldown=3600, poster=fake_post)
    await cost_alerts.maybe_send_alerts(alerts, url="http://x", cooldown=3600, poster=fake_post)
    assert calls == ["daily"]


@pytest.mark.asyncio
async def test_no_url_skips():
    calls = []

    async def fake_post(url, payload):
        calls.append(1)
        return True

    alerts = {"daily": {"level": "breached"}}
    sent = await cost_alerts.maybe_send_alerts(alerts, url="", cooldown=60, poster=fake_post)
    assert sent == []
    assert calls == []


@pytest.mark.asyncio
async def test_ok_level_not_sent():
    calls = []

    async def fake_post(url, payload):
        calls.append(1)
        return True

    alerts = {"daily": {"level": "ok"}, "monthly": {"level": "warn"}}
    sent = await cost_alerts.maybe_send_alerts(alerts, url="http://x", cooldown=60, poster=fake_post)
    assert sent == []
    assert calls == []


@pytest.mark.asyncio
async def test_failed_post_not_marked():
    calls = []

    async def fake_post(url, payload):
        calls.append(payload["key"])
        return False  # 模拟失败

    alerts = {"daily": {"level": "breached", "used_usd": 12.0, "limit_usd": 10.0, "ratio": 1.2}}
    await cost_alerts.maybe_send_alerts(alerts, url="http://x", cooldown=3600, poster=fake_post)
    # 失败不应标记，再次调用还会尝试
    await cost_alerts.maybe_send_alerts(alerts, url="http://x", cooldown=3600, poster=fake_post)
    assert calls == ["daily", "daily"]


def _admin(uid: int = 1) -> User:
    return User(id=uid, username="admin", is_admin=True, password_hash="x")


@pytest.mark.asyncio
async def test_admin_can_get_and_update_cost_alert_settings():
    old = (
        settings.LLM_DAILY_USD_LIMIT,
        settings.LLM_MONTHLY_USD_LIMIT,
        settings.LLM_ALERT_WEBHOOK_URL,
        settings.LLM_ALERT_WEBHOOK_COOLDOWN_SEC,
    )
    try:
        settings.LLM_DAILY_USD_LIMIT = 1.0
        settings.LLM_MONTHLY_USD_LIMIT = 30.0
        settings.LLM_ALERT_WEBHOOK_URL = ""
        settings.LLM_ALERT_WEBHOOK_COOLDOWN_SEC = 60

        current = await get_cost_alert_settings(admin=_admin())
        assert current["llm_daily_usd_limit"] == 1.0
        assert current["llm_monthly_usd_limit"] == 30.0
        assert current["llm_alert_webhook_url"] == ""
        assert current["llm_alert_webhook_cooldown_sec"] == 60

        updated = await update_cost_alert_settings(
            data={
                "llm_daily_usd_limit": 2.5,
                "llm_monthly_usd_limit": 99.0,
                "llm_alert_webhook_url": "https://example.com/hook",
                "llm_alert_webhook_cooldown_sec": 180,
            },
            admin=_admin(),
        )
        assert updated["llm_daily_usd_limit"] == 2.5
        assert updated["llm_monthly_usd_limit"] == 99.0
        assert updated["llm_alert_webhook_url"] == "https://example.com/hook"
        assert updated["llm_alert_webhook_cooldown_sec"] == 180
    finally:
        (
            settings.LLM_DAILY_USD_LIMIT,
            settings.LLM_MONTHLY_USD_LIMIT,
            settings.LLM_ALERT_WEBHOOK_URL,
            settings.LLM_ALERT_WEBHOOK_COOLDOWN_SEC,
        ) = old


@pytest.mark.asyncio
async def test_update_cost_alert_settings_rejects_invalid_url():
    with pytest.raises(HTTPException) as exc:
        await update_cost_alert_settings(
            data={"llm_alert_webhook_url": "ftp://bad"},
            admin=_admin(),
        )
    assert exc.value.status_code == 400
