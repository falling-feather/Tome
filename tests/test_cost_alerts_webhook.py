"""v2.20: 费用告警 Webhook 推送。"""
import pytest

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
