"""v2.12: hourly bucket flush + trend aggregation."""
import datetime as _dt
import pytest

from backend.app.services import cost as cost_mod


@pytest.mark.asyncio
async def test_flush_pending_and_trend(db_session):
    cost_mod.reset_usage()
    cost_mod.record_usage("gpt-4o", 1000, 500)
    cost_mod.record_usage("gpt-4o-mini", 200, 100)

    n = await cost_mod.flush_pending_to_db(db_session)
    assert n == 2

    points = await cost_mod.get_usage_trend(db_session, hours=24)
    assert len(points) >= 1
    p = points[-1]
    assert p["requests"] == 2
    assert p["input_tokens"] == 1200
    assert p["output_tokens"] == 600
    assert p["cost_usd"] > 0


@pytest.mark.asyncio
async def test_flush_idempotent_accumulates(db_session):
    cost_mod.reset_usage()
    cost_mod.record_usage("deepseek-chat", 100, 50)
    await cost_mod.flush_pending_to_db(db_session)
    cost_mod.record_usage("deepseek-chat", 200, 100)
    await cost_mod.flush_pending_to_db(db_session)
    points = await cost_mod.get_usage_trend(db_session, hours=24)
    p = points[-1]
    assert p["requests"] == 2
    assert p["input_tokens"] == 300
    assert p["output_tokens"] == 150
