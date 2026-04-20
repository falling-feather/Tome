"""
五级记忆压缩服务

L1 - 原始消息: 保留最近 N 条完整消息 (由 LLM 调用时直接使用)
L2 - 近期摘要: 将较早的消息压缩为段落摘要
L3 - 章节摘要: 章节结束时压缩为章节总结
L4 - 弧线摘要: 多章节压缩为故事弧总结
L5 - 核心记忆: 永久保存的关键事实
"""
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, delete

from backend.app.models import MemoryEntry, Message

logger = logging.getLogger("inkless")

# ---------------------------------------------------------------------------
# 配置常量
# ---------------------------------------------------------------------------
L1_RAW_LIMIT = 8            # L1: 保留最近8条原始消息送入 LLM
L2_TRIGGER = 16             # L2: 当消息数 > 16 时触发压缩
L2_BATCH_SIZE = 10          # L2: 每次压缩 10 条消息
L3_TRIGGER_CHAPTER = True   # L3: 章节变更时触发
L4_TRIGGER_CHAPTERS = 3     # L4: 每积累 3 个 L3 摘要时触发
L5_TRIGGER_ARCS = 2         # L5: 每积累 2 个 L4 摘要时触发

# Token 预算 (每级)
TOKEN_BUDGET = {
    2: 300,   # L2 摘要 ≈ 300 tokens
    3: 200,   # L3 章节摘要 ≈ 200 tokens
    4: 150,   # L4 弧线摘要 ≈ 150 tokens
    5: 100,   # L5 核心记忆 ≈ 100 tokens
}


class MemoryService:
    """五级记忆压缩管理器"""

    def __init__(self, session_id: str, db: AsyncSession):
        self.session_id = session_id
        self.db = db

    # ------------------------------------------------------------------
    # 压缩触发检查 (每回合调用)
    # ------------------------------------------------------------------
    async def check_and_compress(self, state: dict, llm_complete=None):
        """
        检查是否需要触发各级压缩。
        llm_complete: async callable(prompt, max_tokens) -> str  用于 LLM 摘要
        """
        turn = state.get("turn", 0)
        chapter = state.get("chapter", 1)

        # L2: 消息数量触发
        msg_count = await self._count_messages()
        if msg_count > L2_TRIGGER:
            await self._compress_l2(turn, llm_complete)

        # L3: 章节变更触发
        last_l3_chapter = await self._last_chapter_compressed()
        if chapter > last_l3_chapter:
            await self._compress_l3(chapter - 1, llm_complete)

        # L4: L3 积累触发
        l3_count = await self._count_level(3)
        l4_count = await self._count_level(4)
        if l3_count >= L4_TRIGGER_CHAPTERS and l3_count > l4_count * L4_TRIGGER_CHAPTERS:
            await self._compress_l4(llm_complete)

        # L5: L4 积累触发
        if l4_count >= L5_TRIGGER_ARCS:
            l5_count = await self._count_level(5)
            if l5_count == 0:
                await self._compress_l5(llm_complete)

    # ------------------------------------------------------------------
    # 记忆检索 (构建上下文用)
    # ------------------------------------------------------------------
    async def retrieve_context(self, max_chars: int = 2000) -> str:
        """
        从各级记忆中组装上下文，按级别从高到低:
        L5 → L4 → L3 → L2
        (L1 由调用方直接从 Message 表获取)
        """
        from backend.app.tracing import traced_span
        with traced_span("memory.retrieve_context", session_id=self.session_id, max_chars=max_chars):
            parts = []
            remaining = max_chars

            for level in [5, 4, 3, 2]:
                if remaining <= 100:
                    break

                result = await self.db.execute(
                    select(MemoryEntry).where(and_(
                        MemoryEntry.session_id == self.session_id,
                        MemoryEntry.level == level,
                    )).order_by(MemoryEntry.turn_end.desc()).limit(3)
                )
                entries = list(reversed(result.scalars().all()))

                for entry in entries:
                    if remaining <= 50:
                        break
                    text = entry.content[:remaining]
                    label = self._level_label(level)
                    parts.append(f"[{label}] {text}")
                    remaining -= len(text)

            if not parts:
                return ""

            return "## 记忆回顾\n" + "\n".join(parts)

    # ------------------------------------------------------------------
    # L2 压缩: 近期消息 → 段落摘要
    # ------------------------------------------------------------------
    async def _compress_l2(self, current_turn: int, llm_complete=None):
        """压缩较早的消息为 L2 摘要"""
        # 获取所有消息，跳过最新的 L1_RAW_LIMIT 条
        result = await self.db.execute(
            select(Message).where(Message.session_id == self.session_id)
            .order_by(Message.created_at).limit(L2_BATCH_SIZE)
        )
        old_messages = result.scalars().all()

        if len(old_messages) < L2_BATCH_SIZE:
            return

        # 用文本形式准备摘要输入
        msg_text = "\n".join(
            f"[{m.role}] {m.content[:200]}" for m in old_messages
        )

        summary = await self._summarize(
            msg_text,
            "请将以下游戏对话压缩为一段简明的叙事摘要（150字以内），"
            "保留关键事件、地点变化和人物互动：",
            max_tokens=TOKEN_BUDGET[2],
            llm_complete=llm_complete,
        )

        if summary:
            # 保存 L2 摘要
            entry = MemoryEntry(
                session_id=self.session_id,
                level=2,
                content=summary,
                turn_start=0,
                turn_end=current_turn,
                token_estimate=len(summary),
                metadata_={"msg_count": len(old_messages)},
            )
            self.db.add(entry)

            # 删除已压缩的原始消息 (保留最新的)
            for msg in old_messages:
                await self.db.delete(msg)

            await self.db.commit()
            logger.info(f"L2 压缩完成: {len(old_messages)} 消息 → 摘要")

    # ------------------------------------------------------------------
    # L3 压缩: 章节结束 → 章节摘要
    # ------------------------------------------------------------------
    async def _compress_l3(self, chapter: int, llm_complete=None):
        """将指定章节的 L2 摘要 + 剩余消息压缩为 L3 章节摘要"""
        # 收集该章节的所有 L2 摘要
        result = await self.db.execute(
            select(MemoryEntry).where(and_(
                MemoryEntry.session_id == self.session_id,
                MemoryEntry.level == 2,
            )).order_by(MemoryEntry.turn_end)
        )
        l2_entries = result.scalars().all()

        if not l2_entries:
            return

        l2_text = "\n".join(e.content for e in l2_entries)

        summary = await self._summarize(
            l2_text,
            f"请将以下内容压缩为第{chapter}章的章节摘要（100字以内），"
            "保留核心剧情转折、重要发现和角色成长：",
            max_tokens=TOKEN_BUDGET[3],
            llm_complete=llm_complete,
        )

        if summary:
            entry = MemoryEntry(
                session_id=self.session_id,
                level=3,
                content=summary,
                chapter=chapter,
                turn_start=l2_entries[0].turn_start if l2_entries else 0,
                turn_end=l2_entries[-1].turn_end if l2_entries else 0,
                token_estimate=len(summary),
            )
            self.db.add(entry)

            # 清理已压缩的 L2 条目
            for e in l2_entries:
                await self.db.delete(e)

            await self.db.commit()
            logger.info(f"L3 压缩完成: 第{chapter}章")

    # ------------------------------------------------------------------
    # L4 压缩: 多章节 → 故事弧摘要
    # ------------------------------------------------------------------
    async def _compress_l4(self, llm_complete=None):
        """将多个 L3 章节摘要压缩为 L4 弧线摘要"""
        result = await self.db.execute(
            select(MemoryEntry).where(and_(
                MemoryEntry.session_id == self.session_id,
                MemoryEntry.level == 3,
            )).order_by(MemoryEntry.chapter)
        )
        l3_entries = result.scalars().all()

        if len(l3_entries) < L4_TRIGGER_CHAPTERS:
            return

        l3_text = "\n".join(
            f"第{e.chapter}章: {e.content}" for e in l3_entries
        )

        summary = await self._summarize(
            l3_text,
            "请将以下多个章节摘要压缩为一段故事弧总结（80字以内），"
            "保留最核心的冲突和角色发展轨迹：",
            max_tokens=TOKEN_BUDGET[4],
            llm_complete=llm_complete,
        )

        if summary:
            entry = MemoryEntry(
                session_id=self.session_id,
                level=4,
                content=summary,
                chapter=l3_entries[-1].chapter,
                turn_start=l3_entries[0].turn_start,
                turn_end=l3_entries[-1].turn_end,
                token_estimate=len(summary),
            )
            self.db.add(entry)

            for e in l3_entries:
                await self.db.delete(e)

            await self.db.commit()
            logger.info(f"L4 压缩完成: {len(l3_entries)} 章 → 弧线摘要")

    # ------------------------------------------------------------------
    # L5 压缩: 核心记忆 (永久)
    # ------------------------------------------------------------------
    async def _compress_l5(self, llm_complete=None):
        """将 L4 弧线摘要压缩为 L5 核心记忆"""
        result = await self.db.execute(
            select(MemoryEntry).where(and_(
                MemoryEntry.session_id == self.session_id,
                MemoryEntry.level == 4,
            )).order_by(MemoryEntry.turn_end)
        )
        l4_entries = result.scalars().all()

        if not l4_entries:
            return

        l4_text = "\n".join(e.content for e in l4_entries)

        summary = await self._summarize(
            l4_text,
            "请提炼以下冒险经历中最核心的事实（50字以内），"
            "包含：关键抉择、重要发现、角色核心关系。仅保留不可遗忘的信息：",
            max_tokens=TOKEN_BUDGET[5],
            llm_complete=llm_complete,
        )

        if summary:
            entry = MemoryEntry(
                session_id=self.session_id,
                level=5,
                content=summary,
                turn_start=l4_entries[0].turn_start,
                turn_end=l4_entries[-1].turn_end,
                token_estimate=len(summary),
            )
            self.db.add(entry)

            for e in l4_entries:
                await self.db.delete(e)

            await self.db.commit()
            logger.info("L5 核心记忆生成完成")

    # ------------------------------------------------------------------
    # 辅助方法
    # ------------------------------------------------------------------
    async def _summarize(
        self, text: str, instruction: str, max_tokens: int, llm_complete=None
    ) -> str:
        """使用 LLM 摘要。如果不可用则使用截断回退。"""
        if llm_complete:
            try:
                prompt = f"{instruction}\n\n{text}"
                return await llm_complete(prompt, max_tokens)
            except Exception as e:
                logger.warning(f"LLM 摘要失败, 使用回退: {e}")

        # 回退: 简单截断
        max_chars = max_tokens * 2  # 粗略估计
        if len(text) <= max_chars:
            return text
        return text[:max_chars] + "..."

    async def _count_messages(self) -> int:
        result = await self.db.execute(
            select(func.count(Message.id)).where(Message.session_id == self.session_id)
        )
        return result.scalar() or 0

    async def _count_level(self, level: int) -> int:
        result = await self.db.execute(
            select(func.count(MemoryEntry.id)).where(and_(
                MemoryEntry.session_id == self.session_id,
                MemoryEntry.level == level,
            ))
        )
        return result.scalar() or 0

    async def _last_chapter_compressed(self) -> int:
        """获取最后一个已压缩的章节号"""
        result = await self.db.execute(
            select(func.max(MemoryEntry.chapter)).where(and_(
                MemoryEntry.session_id == self.session_id,
                MemoryEntry.level == 3,
            ))
        )
        return result.scalar() or 0

    @staticmethod
    def _level_label(level: int) -> str:
        return {
            2: "近期回顾",
            3: "章节记忆",
            4: "故事弧",
            5: "核心记忆",
        }.get(level, f"L{level}")
