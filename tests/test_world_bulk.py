"""v2.17: 世界书条目批量操作 (enable / disable / delete)。"""
import pytest
from fastapi import HTTPException
from sqlalchemy import select

from backend.app.routers.admin import bulk_world_entries
from backend.app.models import User, WorldEntry


def _admin() -> User:
    return User(id=1, username="admin", is_admin=True, password_hash="x")


async def _seed(db_session) -> list[int]:
    rows = [
        WorldEntry(scenario="*", layer="core", category="lore", title=f"e{i}",
                   keywords="", content="x", chapter_min=0, chapter_max=0,
                   priority=0, is_active=True)
        for i in range(3)
    ]
    for r in rows:
        db_session.add(r)
    await db_session.commit()
    for r in rows:
        await db_session.refresh(r)
    return [r.id for r in rows]


@pytest.mark.asyncio
async def test_bulk_disable(db_session):
    ids = await _seed(db_session)
    res = await bulk_world_entries(
        data={"ids": ids, "action": "disable"}, admin=_admin(), db=db_session,
    )
    assert res == {"action": "disable", "affected": 3, "requested": 3}
    rows = (await db_session.execute(select(WorldEntry))).scalars().all()
    assert all(not r.is_active for r in rows)


@pytest.mark.asyncio
async def test_bulk_delete(db_session):
    ids = await _seed(db_session)
    res = await bulk_world_entries(
        data={"ids": ids[:2], "action": "delete"}, admin=_admin(), db=db_session,
    )
    assert res["affected"] == 2
    remaining = (await db_session.execute(select(WorldEntry))).scalars().all()
    assert len(remaining) == 1


@pytest.mark.asyncio
async def test_bulk_invalid_action(db_session):
    ids = await _seed(db_session)
    with pytest.raises(HTTPException) as exc:
        await bulk_world_entries(
            data={"ids": ids, "action": "xxx"}, admin=_admin(), db=db_session,
        )
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_bulk_empty_ids(db_session):
    with pytest.raises(HTTPException) as exc:
        await bulk_world_entries(
            data={"ids": [], "action": "enable"}, admin=_admin(), db=db_session,
        )
    assert exc.value.status_code == 400
