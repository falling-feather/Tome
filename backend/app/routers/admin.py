from fastapi import APIRouter, Depends, Query, HTTPException, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from backend.app.database import get_db
from backend.app.models import User, GameSession, Message, ActivityLog, WorldEntry, PromptTemplate, GameEvent
from backend.app.services.prompt_assembler import invalidate_template_cache
from backend.app.schemas import LogList, LogEntry, AdminStats, UserInfo
from backend.app.auth import require_admin
from backend.app.services.resilience import (
    llm_circuit_breaker, llm_fallback_circuit_breaker,
    game_rate_limiter, health_metrics, daily_quota,
)

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/stats", response_model=AdminStats)
async def get_stats(admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    total_users = (await db.execute(select(func.count(User.id)))).scalar() or 0
    total_sessions = (await db.execute(select(func.count(GameSession.id)))).scalar() or 0
    total_messages = (await db.execute(select(func.count(Message.id)))).scalar() or 0
    total_logs = (await db.execute(select(func.count(ActivityLog.id)))).scalar() or 0

    recent_result = await db.execute(select(User).order_by(desc(User.created_at)).limit(10))
    recent_users = [
        UserInfo(id=u.id, username=u.username, is_admin=u.is_admin, created_at=u.created_at)
        for u in recent_result.scalars().all()
    ]

    return AdminStats(
        total_users=total_users, total_sessions=total_sessions,
        total_messages=total_messages, total_logs=total_logs,
        recent_users=recent_users,
    )


@router.get("/logs", response_model=LogList)
async def get_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    action: str = Query("", description="过滤操作类型"),
    username: str = Query("", description="过滤用户名"),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    query = select(ActivityLog).order_by(desc(ActivityLog.created_at))

    if action:
        query = query.where(ActivityLog.action == action)
    if username:
        query = query.where(ActivityLog.username.contains(username))

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    logs = result.scalars().all()

    return LogList(
        logs=[
            LogEntry(
                id=l.id, user_id=l.user_id, username=l.username, action=l.action,
                detail=l.detail, ip_address=l.ip_address, user_agent=l.user_agent,
                created_at=l.created_at,
            ) for l in logs
        ],
        total=total, page=page, page_size=page_size,
    )


@router.get("/users")
async def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    total = (await db.execute(select(func.count(User.id)))).scalar() or 0
    result = await db.execute(
        select(User).order_by(desc(User.created_at)).offset((page - 1) * page_size).limit(page_size)
    )
    users = result.scalars().all()
    return {
        "users": [
            {"id": u.id, "username": u.username, "is_admin": u.is_admin, "created_at": u.created_at.isoformat()}
            for u in users
        ],
        "total": total, "page": page, "page_size": page_size,
    }


# ---------------------------------------------------------------------------
# 世界书管理
# ---------------------------------------------------------------------------
@router.get("/world-entries")
async def list_world_entries(
    scenario: str = Query("", description="场景过滤"),
    layer: str = Query("", description="层级过滤"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    query = select(WorldEntry).order_by(WorldEntry.priority.desc(), WorldEntry.id)
    if scenario:
        query = query.where(WorldEntry.scenario == scenario)
    if layer:
        query = query.where(WorldEntry.layer == layer)

    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar() or 0
    result = await db.execute(query.offset((page - 1) * page_size).limit(page_size))
    entries = result.scalars().all()

    return {
        "entries": [
            {
                "id": e.id, "scenario": e.scenario, "layer": e.layer,
                "category": e.category, "title": e.title, "keywords": e.keywords,
                "content": e.content, "chapter_min": e.chapter_min,
                "chapter_max": e.chapter_max, "priority": e.priority,
                "is_active": e.is_active,
            }
            for e in entries
        ],
        "total": total, "page": page, "page_size": page_size,
    }


@router.post("/world-entries")
async def create_world_entry(
    data: dict = Body(...),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    entry = WorldEntry(
        scenario=data.get("scenario", "*"),
        layer=data.get("layer", "core"),
        category=data.get("category", "lore"),
        title=data.get("title", ""),
        keywords=data.get("keywords", ""),
        content=data.get("content", ""),
        chapter_min=data.get("chapter_min", 0),
        chapter_max=data.get("chapter_max", 0),
        priority=data.get("priority", 0),
        is_active=data.get("is_active", True),
    )
    db.add(entry)
    await db.commit()
    await db.refresh(entry)
    # 尝试生成嵌入（失败不阶作）
    try:
        from backend.app.services.world_book import WorldBookService
        svc = WorldBookService(db)
        await svc.embed_entry(entry)
        await db.commit()
    except Exception:
        pass
    return {"id": entry.id, "title": entry.title}


@router.put("/world-entries/{entry_id}")
async def update_world_entry(
    entry_id: int,
    data: dict = Body(...),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(WorldEntry).where(WorldEntry.id == entry_id))
    entry = result.scalar_one_or_none()
    if not entry:
        raise HTTPException(status_code=404, detail="条目不存在")

    for field in ["scenario", "layer", "category", "title", "keywords",
                  "content", "chapter_min", "chapter_max", "priority", "is_active"]:
        if field in data:
            setattr(entry, field, data[field])
    # 内容变动后清空嵌入并尝试重生成
    if any(k in data for k in ("title", "keywords", "content")):
        entry.embedding = None
        try:
            from backend.app.services.world_book import WorldBookService
            svc = WorldBookService(db)
            await svc.embed_entry(entry)
        except Exception:
            pass
    await db.commit()
    return {"status": "ok"}


@router.delete("/world-entries/{entry_id}")
async def delete_world_entry(
    entry_id: int,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(WorldEntry).where(WorldEntry.id == entry_id))
    entry = result.scalar_one_or_none()
    if not entry:
        raise HTTPException(status_code=404, detail="条目不存在")
    await db.delete(entry)
    await db.commit()
    return {"status": "ok"}


@router.post("/world-entries/reembed")
async def reembed_world_entries(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """为所有未生成嵌入的世界书条目批量生成。"""
    from backend.app.services.world_book import WorldBookService
    svc = WorldBookService(db)
    return await svc.reembed_all()


# ---------------------------------------------------------------------------
# 游戏事件池管理
# ---------------------------------------------------------------------------
@router.get("/game-events")
async def list_game_events(
    category: str = Query("", description="事件分类过滤"),
    scenario: str = Query("", description="场景过滤"),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    query = select(GameEvent).order_by(GameEvent.category, GameEvent.id)
    if category:
        query = query.where(GameEvent.category == category)

    result = await db.execute(query)
    events = result.scalars().all()
    if scenario:
        events = [e for e in events if not e.scenarios or scenario in e.scenarios]

    return {
        "events": [
            {
                "id": e.id,
                "event_key": e.event_key,
                "category": e.category,
                "title": e.title,
                "description": e.description,
                "conditions": e.conditions,
                "base_weight": e.base_weight,
                "cooldown_turns": e.cooldown_turns,
                "effects": e.effects,
                "scenarios": e.scenarios or [],
            }
            for e in events
        ]
    }


@router.post("/game-events")
async def create_game_event(
    data: dict = Body(...),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    event = GameEvent(
        event_key=data.get("event_key", ""),
        category=data.get("category", "plot"),
        title=data.get("title", ""),
        description=data.get("description", ""),
        conditions=data.get("conditions", {}),
        base_weight=data.get("base_weight", 1.0),
        cooldown_turns=data.get("cooldown_turns", 3),
        effects=data.get("effects", {}),
        scenarios=data.get("scenarios", []),
    )
    db.add(event)
    await db.commit()
    await db.refresh(event)
    return {"id": event.id, "event_key": event.event_key}


@router.put("/game-events/{event_id}")
async def update_game_event(
    event_id: int,
    data: dict = Body(...),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(GameEvent).where(GameEvent.id == event_id))
    event = result.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=404, detail="事件不存在")

    for field in [
        "event_key", "category", "title", "description", "conditions",
        "base_weight", "cooldown_turns", "effects", "scenarios",
    ]:
        if field in data:
            setattr(event, field, data[field])
    await db.commit()
    return {"status": "ok"}


@router.delete("/game-events/{event_id}")
async def delete_game_event(
    event_id: int,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(GameEvent).where(GameEvent.id == event_id))
    event = result.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=404, detail="事件不存在")
    await db.delete(event)
    await db.commit()
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Prompt 模板管理
# ---------------------------------------------------------------------------
@router.get("/prompt-templates")
async def list_prompt_templates(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(PromptTemplate).where(PromptTemplate.is_active == True)
        .order_by(PromptTemplate.name, PromptTemplate.version.desc())
    )
    templates = result.scalars().all()
    return {
        "templates": [
            {
                "id": t.id, "name": t.name, "scenario": t.scenario,
                "version": t.version, "content": t.content, "is_active": t.is_active,
            }
            for t in templates
        ]
    }


@router.put("/prompt-templates/{template_id}")
async def update_prompt_template(
    template_id: int,
    data: dict = Body(...),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(PromptTemplate).where(PromptTemplate.id == template_id))
    tpl = result.scalar_one_or_none()
    if not tpl:
        raise HTTPException(status_code=404, detail="模板不存在")

    if "content" in data:
        # 版本化：创建新版本而非覆盖
        tpl.is_active = False
        new_tpl = PromptTemplate(
            name=tpl.name,
            scenario=tpl.scenario,
            version=tpl.version + 1,
            content=data["content"],
            is_active=True,
        )
        db.add(new_tpl)
    await db.commit()
    invalidate_template_cache()
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# 健康与指标端点
# ---------------------------------------------------------------------------
@router.get("/health")
async def get_health(admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    """系统健康报告"""
    from backend.app.services.cost import compute_cost_report, flush_pending_to_db, get_cost_alerts
    try:
        await flush_pending_to_db(db)
    except Exception:
        pass
    try:
        cost_alerts = await get_cost_alerts(db)
    except Exception:
        cost_alerts = None
    return {
        "circuit_breakers": {
            "llm_primary": llm_circuit_breaker.get_stats(),
            "llm_fallback": llm_fallback_circuit_breaker.get_stats(),
        },
        "rate_limiter": game_rate_limiter.get_stats(),
        "daily_quota": daily_quota.get_stats(),
        "metrics": health_metrics.get_report(),
        "llm_cost": compute_cost_report(),
        "cost_alerts": cost_alerts,
    }


@router.get("/llm-trend")
async def get_llm_trend(
    hours: int = 24,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """近 N 小时 LLM 调用与费用趋势 (默认 24h)"""
    from backend.app.services.cost import flush_pending_to_db, get_usage_trend
    try:
        await flush_pending_to_db(db)
    except Exception:
        pass
    hours = max(1, min(int(hours or 24), 24 * 30))  # cap 30 days
    points = await get_usage_trend(db, hours=hours)
    return {"hours": hours, "points": points}


@router.get("/llm-export")
async def export_llm_usage(
    days: int = 7,
    fmt: str = "csv",
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """导出最近 N 天 LLM 使用明细（按 hour_bucket+model 行），格式 csv 或 json。"""
    import datetime as _dt
    from fastapi.responses import Response, JSONResponse
    from backend.app.services.cost import flush_pending_to_db
    from backend.app.models import LlmUsageHour

    fmt = (fmt or "csv").lower()
    if fmt not in ("csv", "json"):
        raise HTTPException(status_code=400, detail="fmt 必须为 csv 或 json")
    days = max(1, min(int(days or 7), 365))
    try:
        await flush_pending_to_db(db)
    except Exception:
        pass

    cutoff = _dt.datetime.utcnow().replace(minute=0, second=0, microsecond=0) - _dt.timedelta(days=days)
    stmt = (
        select(
            LlmUsageHour.hour_bucket,
            LlmUsageHour.model,
            LlmUsageHour.requests,
            LlmUsageHour.input_tokens,
            LlmUsageHour.output_tokens,
            LlmUsageHour.cost_usd,
        )
        .where(LlmUsageHour.hour_bucket >= cutoff)
        .order_by(LlmUsageHour.hour_bucket.asc(), LlmUsageHour.model.asc())
    )
    rows = (await db.execute(stmt)).all()
    today = _dt.datetime.utcnow().strftime("%Y%m%d")
    if fmt == "json":
        data = [
            {
                "hour_bucket": r.hour_bucket.isoformat() + "Z",
                "model": r.model,
                "requests": int(r.requests or 0),
                "input_tokens": int(r.input_tokens or 0),
                "output_tokens": int(r.output_tokens or 0),
                "cost_usd": float(r.cost_usd or 0.0),
            }
            for r in rows
        ]
        return JSONResponse(
            {"days": days, "count": len(data), "rows": data},
            headers={"Content-Disposition": f'attachment; filename="llm-usage-{today}.json"'},
        )
    # csv
    import io, csv
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["hour_bucket_utc", "model", "requests", "input_tokens", "output_tokens", "cost_usd"])
    for r in rows:
        w.writerow([
            r.hour_bucket.isoformat() + "Z",
            r.model,
            int(r.requests or 0),
            int(r.input_tokens or 0),
            int(r.output_tokens or 0),
            f"{float(r.cost_usd or 0.0):.6f}",
        ])
    return Response(
        content=buf.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="llm-usage-{today}.csv"'},
    )
