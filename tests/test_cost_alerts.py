"""v2.13: cost threshold alerts."""
import datetime as _dt

import pytest

from backend.app.config import settings
from backend.app.services import cost as cost_mod
from backend.app.models import LlmUsageHour


@pytest.mark.asyncio
async def test_cost_alerts_off_when_no_limit(db_session, monkeypatch):
    monkeypatch.setattr(settings, "LLM_DAILY_USD_LIMIT", 0.0)
    monkeypatch.setattr(settings, "LLM_MONTHLY_USD_LIMIT", 0.0)
    alerts = await cost_mod.get_cost_alerts(db_session)
    assert alerts["daily"]["level"] == "off"
    assert alerts["monthly"]["level"] == "off"


@pytest.mark.asyncio
async def test_cost_alerts_breached_when_used_over_limit(db_session, monkeypatch):
    now = _dt.datetime.utcnow().replace(minute=0, second=0, microsecond=0)
    db_session.add(LlmUsageHour(
        hour_bucket=now,
        model="gpt-4o",
        requests=1,
        input_tokens=10,
        output_tokens=5,
        cost_usd=2.5,
    ))
    await db_session.commit()

    monkeypatch.setattr(settings, "LLM_DAILY_USD_LIMIT", 1.0)
    monkeypatch.setattr(settings, "LLM_MONTHLY_USD_LIMIT", 100.0)
    alerts = await cost_mod.get_cost_alerts(db_session)
    assert alerts["daily"]["level"] == "breached"
    assert alerts["daily"]["used_usd"] >= 2.5
    assert alerts["daily"]["remaining_usd"] == 0.0
    assert alerts["monthly"]["level"] == "ok"


@pytest.mark.asyncio
async def test_cost_alerts_warn_at_80_percent(db_session, monkeypatch):
    now = _dt.datetime.utcnow().replace(minute=0, second=0, microsecond=0)
    db_session.add(LlmUsageHour(
        hour_bucket=now,
        model="gpt-4o",
        requests=1,
        input_tokens=10,
        output_tokens=5,
        cost_usd=0.85,
    ))
    await db_session.commit()

    monkeypatch.setattr(settings, "LLM_DAILY_USD_LIMIT", 1.0)
    monkeypatch.setattr(settings, "LLM_MONTHLY_USD_LIMIT", 0.0)
    alerts = await cost_mod.get_cost_alerts(db_session)
    assert alerts["daily"]["level"] == "warn"
    assert 0.80 <= alerts["daily"]["ratio"] < 1.0
