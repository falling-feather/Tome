"""v2.19: AdminGameEvents/AdminUsers 批量操作。"""
import pytest
from fastapi import HTTPException
from sqlalchemy import select

from backend.app.routers.admin import bulk_game_events, bulk_users
from backend.app.models import User, GameEvent


def _admin(uid: int = 1) -> User:
    return User(id=uid, username="admin", is_admin=True, password_hash="x")


async def _seed_events(db_session) -> list[int]:
    rows = [
        GameEvent(event_key=f"k{i}", category="plot", title=f"e{i}",
                  description="x", conditions={}, base_weight=1.0,
                  cooldown_turns=3, effects={}, scenarios=[])
        for i in range(3)
    ]
    for r in rows:
        db_session.add(r)
    await db_session.commit()
    for r in rows:
        await db_session.refresh(r)
    return [r.id for r in rows]


async def _seed_users(db_session) -> list[int]:
    rows = [
        User(username=f"u{i}", password_hash="x", is_admin=False)
        for i in range(3)
    ]
    for r in rows:
        db_session.add(r)
    await db_session.commit()
    for r in rows:
        await db_session.refresh(r)
    return [r.id for r in rows]


# --- game-events bulk ---


@pytest.mark.asyncio
async def test_bulk_events_delete(db_session):
    ids = await _seed_events(db_session)
    res = await bulk_game_events(
        data={"ids": ids[:2], "action": "delete"}, admin=_admin(), db=db_session,
    )
    assert res == {"action": "delete", "affected": 2, "requested": 2}
    remaining = (await db_session.execute(select(GameEvent))).scalars().all()
    assert len(remaining) == 1


@pytest.mark.asyncio
async def test_bulk_events_invalid_action(db_session):
    ids = await _seed_events(db_session)
    with pytest.raises(HTTPException) as exc:
        await bulk_game_events(
            data={"ids": ids, "action": "enable"}, admin=_admin(), db=db_session,
        )
    assert exc.value.status_code == 400


# --- users bulk ---


@pytest.mark.asyncio
async def test_bulk_users_promote(db_session):
    ids = await _seed_users(db_session)
    res = await bulk_users(
        data={"ids": ids, "action": "promote"}, admin=_admin(uid=999), db=db_session,
    )
    assert res == {"action": "promote", "affected": 3, "requested": 3}
    rows = (await db_session.execute(select(User).where(User.id.in_(ids)))).scalars().all()
    assert all(r.is_admin for r in rows)


@pytest.mark.asyncio
async def test_bulk_users_demote_skips_self(db_session):
    ids = await _seed_users(db_session)
    # 先全部提为管理员
    await bulk_users(data={"ids": ids, "action": "promote"}, admin=_admin(uid=999), db=db_session)
    # 现在以 ids[0] 自己作为 admin 去 demote 全部
    self_admin = User(id=ids[0], username="u0", is_admin=True, password_hash="x")
    res = await bulk_users(
        data={"ids": ids, "action": "demote"}, admin=self_admin, db=db_session,
    )
    # 自己被跳过，所以 affected = 2
    assert res["affected"] == 2
    rows = (await db_session.execute(select(User).where(User.id.in_(ids)))).scalars().all()
    by_id = {r.id: r for r in rows}
    assert by_id[ids[0]].is_admin is True  # 自己保留管理员
    assert by_id[ids[1]].is_admin is False
    assert by_id[ids[2]].is_admin is False


@pytest.mark.asyncio
async def test_bulk_users_invalid_action(db_session):
    with pytest.raises(HTTPException) as exc:
        await bulk_users(
            data={"ids": [1], "action": "delete"}, admin=_admin(), db=db_session,
        )
    assert exc.value.status_code == 400
