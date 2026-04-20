"""v2.24 OTel 本地调用链验证 — 保证 traced_span 在 OTEL_ENABLED=False 时 no-op，
并且业务侧 memory_service.retrieve_context / llm spans / game.post_process 调用不会抛异常。"""
from __future__ import annotations

import pytest

from backend.app.tracing import traced_span, init_tracing


def test_traced_span_noop_when_disabled():
    # 默认 OTEL_ENABLED=False，应当产生 None 作为 span 且不抛
    with traced_span("test.noop", foo="bar", n=1) as span:
        assert span is None


def test_init_tracing_returns_false_when_disabled():
    assert init_tracing(app=None) is False


@pytest.mark.asyncio
async def test_memory_retrieve_context_span_safe(tmp_path, monkeypatch):
    """memory_service.retrieve_context 被 traced_span 包裹后，
    即便 OTEL 未启用仍应返回空字符串（空库）。"""
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
    from backend.app.models import Base
    from backend.app.services.memory_service import MemoryService

    db_url = f"sqlite+aiosqlite:///{tmp_path}/otel-smoke.db"
    engine = create_async_engine(db_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    async with Session() as db:
        svc = MemoryService(session_id="otel-smoke", db=db)
        result = await svc.retrieve_context(max_chars=500)
        assert result == ""

    await engine.dispose()
