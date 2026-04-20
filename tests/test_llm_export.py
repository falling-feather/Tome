"""v2.14: LLM 用量导出 (CSV/JSON)。"""
import datetime as _dt

import pytest

from backend.app.routers.admin import export_llm_usage
from backend.app.models import LlmUsageHour, User


@pytest.mark.asyncio
async def test_export_llm_usage_csv(db_session):
    now = _dt.datetime.utcnow().replace(minute=0, second=0, microsecond=0)
    db_session.add(LlmUsageHour(
        hour_bucket=now, model="gpt-4o", requests=2, input_tokens=100, output_tokens=50, cost_usd=0.0125,
    ))
    await db_session.commit()
    fake_admin = User(id=1, username="admin", is_admin=True, password_hash="x")
    resp = await export_llm_usage(days=1, fmt="csv", admin=fake_admin, db=db_session)
    text = resp.body.decode("utf-8")
    assert text.startswith("hour_bucket_utc,model,requests,input_tokens,output_tokens,cost_usd")
    assert "gpt-4o" in text
    assert "0.012500" in text
    assert resp.headers["Content-Disposition"].startswith("attachment;")
    assert resp.media_type.startswith("text/csv")


@pytest.mark.asyncio
async def test_export_llm_usage_json(db_session):
    now = _dt.datetime.utcnow().replace(minute=0, second=0, microsecond=0)
    db_session.add(LlmUsageHour(
        hour_bucket=now, model="deepseek-chat", requests=1, input_tokens=10, output_tokens=5, cost_usd=0.0001,
    ))
    await db_session.commit()
    fake_admin = User(id=1, username="admin", is_admin=True, password_hash="x")
    resp = await export_llm_usage(days=7, fmt="json", admin=fake_admin, db=db_session)
    import json
    body = json.loads(resp.body.decode("utf-8"))
    assert body["days"] == 7
    assert body["count"] >= 1
    assert any(r["model"] == "deepseek-chat" for r in body["rows"])


@pytest.mark.asyncio
async def test_export_llm_usage_invalid_fmt(db_session):
    from fastapi import HTTPException
    fake_admin = User(id=1, username="admin", is_admin=True, password_hash="x")
    with pytest.raises(HTTPException):
        await export_llm_usage(days=1, fmt="xml", admin=fake_admin, db=db_session)
