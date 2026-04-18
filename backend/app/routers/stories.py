"""
自编故事 API — 导入/查看/删除用户故事
"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

from backend.app.database import get_db, async_session
from backend.app.models import User, CustomStory
from backend.app.auth import get_current_user

router = APIRouter(prefix="/api/stories", tags=["stories"])


# ---- Schemas ----
class StoryImport(BaseModel):
    title: str = "未命名故事"
    content: str = Field(..., min_length=50, max_length=50000)


class StoryInfo(BaseModel):
    id: int
    title: str
    status: str
    error_msg: str = ""
    parsed_data: Optional[dict] = None
    created_at: datetime


class StoryListResponse(BaseModel):
    stories: List[StoryInfo]


# ---- Background parsing task ----
async def _bg_parse(story_id: int, user_id: int):
    """在后台解析故事内容"""
    from backend.app.services.story_import import StoryImportService
    from backend.app.services.llm_service import LLMService

    async with async_session() as db:
        result = await db.execute(select(CustomStory).where(CustomStory.id == story_id))
        story = result.scalar_one_or_none()
        if not story:
            return

        llm = LLMService(user_id=user_id, db=db)
        await llm.load_user_keys()

        svc = StoryImportService(db)
        try:
            await svc.parse_story(story, llm.simple_completion)
            # 解析成功后自动创建世界书条目
            await svc.create_world_entries(story)
        except Exception:
            pass  # 状态已在 service 中更新


# ---- Endpoints ----
@router.post("", response_model=StoryInfo)
async def import_story(
    data: StoryImport,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """导入一个新故事，后台自动解析"""
    # 限制每用户故事数
    count_result = await db.execute(
        select(CustomStory.id).where(CustomStory.user_id == user.id)
    )
    if len(count_result.all()) >= 20:
        raise HTTPException(status_code=400, detail="最多保存 20 个故事")

    story = CustomStory(
        user_id=user.id,
        title=data.title[:256],
        raw_content=data.content,
        status="pending",
    )
    db.add(story)
    await db.commit()
    await db.refresh(story)

    # 启动后台解析
    background_tasks.add_task(_bg_parse, story.id, user.id)

    return StoryInfo(
        id=story.id, title=story.title, status=story.status,
        created_at=story.created_at,
    )


@router.get("", response_model=StoryListResponse)
async def list_stories(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(CustomStory)
        .where(CustomStory.user_id == user.id)
        .order_by(CustomStory.created_at.desc())
    )
    stories = result.scalars().all()
    return StoryListResponse(stories=[
        StoryInfo(
            id=s.id, title=s.title, status=s.status,
            error_msg=s.error_msg or "",
            parsed_data=s.parsed_data if s.status == "ready" else None,
            created_at=s.created_at,
        ) for s in stories
    ])


@router.get("/{story_id}", response_model=StoryInfo)
async def get_story(
    story_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(CustomStory).where(CustomStory.id == story_id, CustomStory.user_id == user.id)
    )
    story = result.scalar_one_or_none()
    if not story:
        raise HTTPException(status_code=404, detail="故事不存在")

    return StoryInfo(
        id=story.id, title=story.title, status=story.status,
        error_msg=story.error_msg or "",
        parsed_data=story.parsed_data,
        created_at=story.created_at,
    )


@router.delete("/{story_id}")
async def delete_story(
    story_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(CustomStory).where(CustomStory.id == story_id, CustomStory.user_id == user.id)
    )
    story = result.scalar_one_or_none()
    if not story:
        raise HTTPException(status_code=404, detail="故事不存在")

    await db.delete(story)
    await db.commit()
    return {"status": "ok"}
