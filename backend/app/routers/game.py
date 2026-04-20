from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse, PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
import json
import logging
import time as _time
from urllib.parse import quote

from backend.app.database import get_db
from backend.app.models import User, GameSession, Message, CustomStory
from backend.app.schemas import (
    SessionCreate, SessionInfo, SessionList, ActionInput, MessageOut, ChatHistory,
    SessionRename
)
from backend.app.auth import get_current_user
from backend.app.audit import audit_log
from backend.app.services.game_engine import GameEngine, SCENARIOS, load_events_from_db
from backend.app.services.llm_service import LLMService
from backend.app.services.post_processor import ResponsePostProcessor
from backend.app.services.memory_service import MemoryService
from backend.app.services.agents import AgentOrchestrator
from backend.app.services.resilience import game_rate_limiter, health_metrics, daily_quota

logger = logging.getLogger("inkless")

router = APIRouter(prefix="/api/game", tags=["game"])


@router.post("/sessions", response_model=SessionInfo)
async def create_session(
    data: SessionCreate, request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    engine = GameEngine()
    scenario = data.scenario

    # 自编故事模式
    custom_intro = None
    if data.story_id:
        story_result = await db.execute(
            select(CustomStory).where(CustomStory.id == data.story_id, CustomStory.user_id == user.id)
        )
        story = story_result.scalar_one_or_none()
        if not story or story.status != "ready":
            raise HTTPException(status_code=400, detail="故事尚未解析完成或不存在")
        scenario = f"custom_{story.id}"
        parsed = story.parsed_data or {}
        # 用故事的地点覆盖默认地点
        locations = [loc["name"] for loc in parsed.get("locations", [])[:6]]
        if locations:
            SCENARIOS[scenario] = {
                "name": story.title,
                "intro": parsed.get("opening_scene", parsed.get("plot_summary", story.title)),
                "locations": locations,
            }
        custom_intro = parsed.get("opening_scene")

    initial_state = engine.create_initial_state(data.character_name, data.character_class, scenario)
    if data.story_id:
        initial_state["story_id"] = data.story_id

    session = GameSession(
        user_id=user.id,
        title=data.title,
        scenario=scenario,
        state=initial_state,
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)

    intro = custom_intro or engine.generate_intro(initial_state)
    msg = Message(session_id=session.id, role="assistant", content=intro)
    db.add(msg)
    await db.commit()

    await audit_log(db, user=user, action="create_session",
                    detail=f"创建游戏会话: {data.title}", request=request)

    return SessionInfo(
        id=session.id, title=session.title, scenario=session.scenario,
        state=session.state, created_at=session.created_at, updated_at=session.updated_at,
    )


@router.get("/sessions", response_model=SessionList)
async def list_sessions(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(GameSession)
        .where(GameSession.user_id == user.id)
        .order_by(GameSession.updated_at.desc())
    )
    sessions = result.scalars().all()
    return SessionList(sessions=[
        SessionInfo(
            id=s.id, title=s.title, scenario=s.scenario,
            state=s.state or {}, created_at=s.created_at, updated_at=s.updated_at,
        ) for s in sessions
    ])


@router.get("/sessions/{session_id}", response_model=ChatHistory)
async def get_session(session_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(GameSession).where(GameSession.id == session_id, GameSession.user_id == user.id)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    msg_result = await db.execute(
        select(Message).where(Message.session_id == session_id).order_by(Message.created_at)
    )
    messages = msg_result.scalars().all()

    return ChatHistory(
        messages=[MessageOut(id=m.id, role=m.role, content=m.content, metadata_=m.metadata_, created_at=m.created_at) for m in messages],
        state=session.state or {},
    )


@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: str, request: Request,
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(GameSession).where(GameSession.id == session_id, GameSession.user_id == user.id)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    await db.delete(session)
    await db.commit()
    await audit_log(db, user=user, action="delete_session",
                    detail=f"删除游戏会话: {session.title}", request=request)
    return {"status": "ok"}


@router.patch("/sessions/{session_id}")
async def rename_session(
    session_id: str, data: SessionRename, request: Request,
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(GameSession).where(GameSession.id == session_id, GameSession.user_id == user.id)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    session.title = data.title
    await db.commit()
    return {"status": "ok", "title": data.title}


@router.post("/sessions/{session_id}/action")
async def submit_action(
    session_id: str, data: ActionInput, request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # 限流检查
    allowed, rate_msg = game_rate_limiter.check(user.id)
    if not allowed:
        raise HTTPException(status_code=429, detail=rate_msg)

    # 每日配额检查
    allowed, quota_msg = daily_quota.check(user.id)
    if not allowed:
        raise HTTPException(status_code=429, detail=quota_msg)

    health_metrics.inc("game_actions")

    result = await db.execute(
        select(GameSession).where(GameSession.id == session_id, GameSession.user_id == user.id)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    engine = GameEngine()
    state = session.state or {}

    # Validate action
    is_valid, reason = engine.validate_action(state, data.content)
    if not is_valid:
        # Return validation error as SSE
        async def reject():
            yield f"data: {json.dumps({'content': f'【系统】{reason}', 'done': True, 'error': True, 'state': state}, ensure_ascii=False)}\n\n"
        return StreamingResponse(reject(), media_type="text/event-stream")

    # Save user message
    user_msg = Message(session_id=session_id, role="user", content=data.content)
    db.add(user_msg)
    await db.commit()
    daily_quota.record(user.id)

    # Get recent messages for context
    msg_result = await db.execute(
        select(Message).where(Message.session_id == session_id).order_by(Message.created_at.desc()).limit(20)
    )
    recent_messages = list(reversed(msg_result.scalars().all()))

    # Check for event triggers (returns narrative + log)
    db_events = await load_events_from_db(db)
    event_narrative, event_log = engine.check_events(state, events=db_events)

    # Build prompt context
    history = [{"role": m.role, "content": m.content} for m in recent_messages]

    llm = LLMService(user_id=user.id, db=db)
    await llm.load_user_keys()

    async def generate():
        _start = _time.time()
        full_response = ""
        try:
            async for chunk in llm.stream_narrative(state, history, data.content, event_narrative, session_id):
                full_response += chunk
                yield f"data: {json.dumps({'content': chunk}, ensure_ascii=False)}\n\n"

            # Post-process the response
            processor = ResponsePostProcessor()
            post_result = processor.process(full_response, state)
            cleaned_text = post_result["cleaned_text"]
            extracted = post_result["extracted"]

            # 多智能体审计
            orchestrator = AgentOrchestrator()
            audit_result = await orchestrator.process(cleaned_text, state, llm.simple_completion)
            if audit_result.was_rewritten:
                cleaned_text = audit_result.final_text
                # 对重写文本重新提取
                post_result = processor.process(cleaned_text, state)
                extracted = post_result["extracted"]

            # Update state with event log
            new_state = engine.update_state(state, data.content, cleaned_text, event_log, events=db_events)

            # Apply extracted info to state
            if extracted["items_gained"]:
                inv = list(new_state.get("inventory", []))
                for item in extracted["items_gained"]:
                    if item not in inv:
                        inv.append(item)
                new_state["inventory"] = inv[:20]  # cap at 20

            if extracted["items_lost"]:
                inv = list(new_state.get("inventory", []))
                for item in extracted["items_lost"]:
                    if item in inv:
                        inv.remove(item)
                new_state["inventory"] = inv

            if extracted["money_spent"]:
                new_state["money"] = max(0, new_state.get("money", 0) - extracted["money_spent"])
            if extracted["money_gained"]:
                new_state["money"] = new_state.get("money", 0) + extracted["money_gained"]

            session.state = new_state
            await db.commit()

            # 触发记忆压缩检查
            try:
                memory_svc = MemoryService(session_id, db)
                await memory_svc.check_and_compress(new_state, llm.simple_completion)
            except Exception as mem_err:
                logger.warning(f"记忆压缩异常: {mem_err}")

            # Save assistant message with event + extraction metadata
            msg_meta = {}
            segments = post_result.get("segments", [])
            if segments:
                msg_meta["segments"] = segments
            if event_log and event_log.get("selected"):
                msg_meta["event"] = event_log["selected"]
            if extracted["items_gained"] or extracted["items_lost"]:
                msg_meta["items"] = {"gained": extracted["items_gained"], "lost": extracted["items_lost"]}
            if extracted["npcs_mentioned"]:
                msg_meta["npcs"] = extracted["npcs_mentioned"]
            if post_result["warnings"]:
                msg_meta["warnings"] = post_result["warnings"]
            if audit_result.total_issues > 0:
                msg_meta["audit"] = {
                    "issues": audit_result.total_issues,
                    "rewritten": audit_result.was_rewritten,
                }

            assistant_msg = Message(
                session_id=session_id, role="assistant",
                content=cleaned_text if cleaned_text != full_response else full_response,
                metadata_=msg_meta,
            )
            db.add(assistant_msg)
            await db.commit()

            yield f"data: {json.dumps({'done': True, 'state': new_state, 'segments': segments}, ensure_ascii=False)}\n\n"
            health_metrics.record_timing("game_action_ms", (_time.time() - _start) * 1000)
        except Exception as e:
            # Fallback response on error
            fallback = f"【系统】叙事生成遇到问题，请重试。错误：{str(e)}"
            fallback_msg = Message(session_id=session_id, role="assistant", content=fallback)
            db.add(fallback_msg)
            await db.commit()
            yield f"data: {json.dumps({'content': fallback, 'done': True, 'error': True}, ensure_ascii=False)}\n\n"

    await audit_log(db, user=user, action="game_action",
                    detail=f"会话 {session_id}: {data.content[:100]}", request=request)

    return StreamingResponse(generate(), media_type="text/event-stream")


@router.get("/sessions/{session_id}/export")
async def export_session(
    session_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """导出游戏会话为 Markdown 格式"""
    result = await db.execute(
        select(GameSession).where(
            GameSession.id == session_id, GameSession.user_id == user.id
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(404, "会话不存在")

    msg_result = await db.execute(
        select(Message)
        .where(Message.session_id == session_id)
        .order_by(Message.created_at)
    )
    msgs = msg_result.scalars().all()

    state = session.state or {}
    char_name = state.get("character_name", "冒险者")
    char_class = state.get("character_class", "")
    scenario_label = session.scenario or ""

    lines: list[str] = []
    lines.append(f"# {session.title}")
    lines.append("")
    lines.append(f"- **世界**: {scenario_label}")
    if char_name:
        lines.append(f"- **角色**: {char_name}" + (f" ({char_class})" if char_class else ""))
    lines.append(f"- **回合数**: {state.get('turn', 0)}")
    lines.append(f"- **导出时间**: {_time.strftime('%Y-%m-%d %H:%M')}")
    lines.append("")
    lines.append("---")
    lines.append("")

    for msg in msgs:
        meta = msg.metadata_ or {}
        segments = meta.get("segments")
        if msg.role == "user":
            lines.append(f"> **{char_name}**: {msg.content}")
            lines.append("")
        elif msg.role == "assistant":
            if segments:
                for seg in segments:
                    speaker = seg.get("speaker", "")
                    text = seg.get("content", "") or seg.get("text", "")
                    if speaker == "narrator" or not speaker:
                        lines.append(f"*{text}*")
                    else:
                        lines.append(f"**{speaker}**: {text}")
                lines.append("")
            else:
                lines.append(msg.content)
                lines.append("")

    markdown = "\n".join(lines)
    safe_title = session.title.replace("/", "_").replace("\\", "_")[:50]
    encoded_filename = quote(f"{safe_title}.md")
    return PlainTextResponse(
        content=markdown,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}"},
    )
