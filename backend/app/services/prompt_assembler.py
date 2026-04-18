"""
Prompt 装配器 — 分层模板管理 + 动静分离装配
"""
import logging
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from backend.app.models import PromptTemplate

logger = logging.getLogger("inkless")


# ---------------------------------------------------------------------------
# 默认 Prompt 模板 (种子)
# ---------------------------------------------------------------------------
DEFAULT_TEMPLATES: list[dict] = [
    {
        "name": "system_core",
        "scenario": "*",
        "version": 1,
        "content": (
            "你是一个互动文字冒险游戏的叙事引擎。"
            "你的角色是为玩家创造沉浸式、生动的冒险体验。\n"
            "## 基本规则\n"
            "1. 以第二人称描述场景和行动结果（\"你走进了...\"）\n"
            "2. 保持叙事风格一致，语言生动但不冗余\n"
            "3. 每次回复控制在200-400字\n"
            "4. 根据玩家的行动合理推进剧情\n"
            "5. 适当设置悬念和选择点\n"
            "6. 如果玩家行为不合理，温和地引导而不是直接拒绝\n"
            "7. 通过叙事暗示数值变化，不要直接显示数值\n"
            "8. 绝对不要在回复末尾列出选项或建议（禁止'你可以...'列表），让玩家自行决定\n"
            "9. 绝对不要使用元叙事（不要说\"作为AI\"、\"游戏里\"等）\n"
            "10. 不要在文本中使用Markdown格式标记（如**加粗**、*斜体*、#标题等），用纯文本叙事"
        ),
    },
    {
        "name": "style_fantasy",
        "scenario": "fantasy",
        "version": 1,
        "content": (
            "## 奇幻风格指南\n"
            "- 描写中可以出现魔法光芒、神秘符文、精灵耳语等奇幻元素\n"
            "- 战斗描写侧重剑与魔法的交织，注重视觉冲击\n"
            "- NPC说话风格偏古典但不晦涩，如\"旅人，你从何处来？\"\n"
            "- 环境描写多用自然意象：古木参天、月光如银、风声呜咽"
        ),
    },
    {
        "name": "style_scifi",
        "scenario": "scifi",
        "version": 1,
        "content": (
            "## 科幻风格指南\n"
            "- 描写中应有科技质感：全息面板、等离子焰、量子涟漪\n"
            "- 飞船内部细节生动：嗡鸣的引擎、闪烁的仪表盘、回收空气的味道\n"
            "- 对话风格偏现代简练，可使用科幻术语但要自然\n"
            "- 太空场景注重宏大感与寂静感的对比"
        ),
    },
    {
        "name": "style_wuxia",
        "scenario": "wuxia",
        "version": 1,
        "content": (
            "## 武侠风格指南\n"
            "- 描写侧重武打的写意感：剑光如虹、掌风呼啸、身法如鬼魅\n"
            "- 对话风格偏古风口语：\"阁下高姓大名？\"、\"承让了。\"\n"
            "- 环境描写融入古典意象：青竹幽径、飞檐翘角、月下长街\n"
            "- 注重江湖情义、恩怨分明的叙事基调"
        ),
    },
    {
        "name": "status_combat",
        "scenario": "*",
        "version": 1,
        "content": (
            "## 战斗场景规则\n"
            "- 保持高节奏和紧张感，每次描写一两个战斗来回\n"
            "- 注意伤痕和体能消耗的细节描写\n"
            "- 战斗不应一击定胜负（除Boss外），留出战术选择空间\n"
            "- 明确描述战斗结束标志（敌人倒下/撤退/双方停战）"
        ),
    },
    {
        "name": "status_dialogue",
        "scenario": "*",
        "version": 1,
        "content": (
            "## 对话场景规则\n"
            "- NPC应有鲜明个性，语气风格各异\n"
            "- 对话中自然地透露有用信息和线索\n"
            "- 允许玩家选择对话方向（友好/威胁/贿赂等）\n"
            "- 重要NPC的好感度会影响后续剧情走向"
        ),
    },
    {
        "name": "status_trading",
        "scenario": "*",
        "version": 1,
        "content": (
            "## 交易场景规则\n"
            "- 描写物品的外观和特色，暗示其价值\n"
            "- 商人有自己的性格和讨价还价风格\n"
            "- 合理控制物价，稀有物品价格要高\n"
            "- 某些物品只能通过特定商人购买"
        ),
    },
    {
        "name": "status_resting",
        "scenario": "*",
        "version": 1,
        "content": (
            "## 休息场景规则\n"
            "- 描写宁静和恢复的氛围\n"
            "- 暗示体力恢复和伤势好转\n"
            "- 可以安排梦境、回忆或偶遇事件\n"
            "- 休息场景不宜太长，1-2轮后引导冒险"
        ),
    },
    {
        "name": "dialogue_format",
        "scenario": "*",
        "version": 1,
        "content": (
            "## 输出格式（严格遵守）\n"
            "你的回复必须使用以下分段标记来区分旁白和角色对话：\n"
            "- 旁白/叙事部分用 [旁白] 开头\n"
            "- 角色说话部分用 [角色:角色名] 开头\n"
            "示例：\n"
            "[旁白]\n"
            "你推开沉重的木门，酒馆内的喧嚣扑面而来。\n\n"
            "[角色:酒馆老板]\n"
            '一个壮硕的中年人抬起头，朝你咧嘴一笑。\u201c嘿，旅人！坐下来喝一杯？\u201d\n\n'
            "[旁白]\n"
            "角落里，一道冰冷的目光正悄悄注视着你。\n\n"
            "注意：\n"
            "- 每次回复至少包含一个 [旁白] 段\n"
            "- 角色对话时把动作描写和台词放在同一段内\n"
            "- 不要为玩家角色生成对话\n"
            "- 标记必须独占一行"
        ),
    },
]


class PromptAssembler:
    """Prompt 装配器 — 组合静态模板 + 世界书知识 + 动态状态"""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ------------------------------------------------------------------
    # 种子数据
    # ------------------------------------------------------------------
    async def seed_if_empty(self):
        result = await self.db.execute(select(PromptTemplate.id).limit(1))
        if result.scalar_one_or_none() is not None:
            return

        for tpl in DEFAULT_TEMPLATES:
            pt = PromptTemplate(
                name=tpl["name"],
                scenario=tpl["scenario"],
                version=tpl["version"],
                content=tpl["content"],
                is_active=True,
            )
            self.db.add(pt)
        await self.db.commit()
        logger.info(f"Prompt 模板种子数据已写入: {len(DEFAULT_TEMPLATES)} 条")

    # ------------------------------------------------------------------
    # 模板获取
    # ------------------------------------------------------------------
    async def get_template(self, name: str, scenario: str = "*") -> str | None:
        """获取指定名称和场景的活跃模板"""
        # 先找场景专用，再找通用
        for sc in [scenario, "*"]:
            result = await self.db.execute(
                select(PromptTemplate).where(and_(
                    PromptTemplate.name == name,
                    PromptTemplate.scenario == sc,
                    PromptTemplate.is_active == True,
                )).order_by(PromptTemplate.version.desc()).limit(1)
            )
            tpl = result.scalar_one_or_none()
            if tpl:
                return tpl.content
        return None

    # ------------------------------------------------------------------
    # 核心装配
    # ------------------------------------------------------------------
    async def assemble(
        self,
        state: dict,
        world_lore: list[dict],
        event_context: str = "",
    ) -> str:
        """
        装配完整 System Prompt，分层结构:
        1. 核心规则 (system_core 模板)
        2. 风格指南 (style_{scenario} 模板)
        3. 世界书知识 (检索结果)
        4. 状态感知上下文 (动态生成)
        5. 当前场景规则 (status_{status} 模板)
        6. 事件注入 (可选)
        """
        scenario = state.get("scenario", "fantasy")
        status = state.get("status", "exploring")
        parts: list[str] = []

        # 1. 核心规则
        core = await self.get_template("system_core")
        if core:
            parts.append(core)

        # 1.5 对话格式规范
        dialogue_fmt = await self.get_template("dialogue_format")
        if dialogue_fmt:
            parts.append(dialogue_fmt)

        # 2. 风格指南
        style = await self.get_template(f"style_{scenario}", scenario)
        if style:
            parts.append(style)

        # 3. 世界书知识
        if world_lore:
            lore_text = self._format_lore(world_lore)
            parts.append(lore_text)

        # 4. 状态感知上下文 (动态)
        state_ctx = self._build_state_context(state)
        parts.append(state_ctx)

        # 5. 状态专用规则
        status_tpl = await self.get_template(f"status_{status}")
        if status_tpl:
            parts.append(status_tpl)

        # 6. 事件注入
        if event_context:
            parts.append(f"## 当前触发事件\n{event_context}")

        prompt = "\n\n".join(parts)

        # 粗略 token 预算控制 (1个中文字 ≈ 1.5 token)
        max_chars = 3000
        if len(prompt) > max_chars:
            prompt = prompt[:max_chars] + "\n...[设定截断]"
            logger.warning(f"Prompt 超长截断: {len(prompt)} chars")

        return prompt

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------
    @staticmethod
    def _format_lore(entries: list[dict]) -> str:
        """格式化世界书检索结果"""
        lines = ["## 世界设定参考"]
        for entry in entries:
            lines.append(f"### {entry['title']}（{entry['category']}）")
            lines.append(entry["content"])
        return "\n".join(lines)

    @staticmethod
    def _build_state_context(state: dict) -> str:
        """动态生成状态上下文"""
        char_name = state.get("character_name", "旅行者")
        char_class = state.get("character_class", "冒险者")
        location = state.get("current_location", "未知之地")
        hp = state.get("health", 100)
        max_hp = state.get("max_health", 100)
        gold = state.get("money", 50)
        fatigue = state.get("fatigue", 0)
        status = state.get("status", "exploring")
        chapter = state.get("chapter", 1)
        turn = state.get("turn", 0)
        inventory = state.get("inventory", [])
        quest_flags = state.get("quest_flags", {})

        status_names = {
            "exploring": "探索中", "combat": "战斗中", "resting": "休息中",
            "trading": "交易中", "dialogue": "对话中", "dead": "已死亡",
        }

        hp_pct = hp / max_hp * 100 if max_hp > 0 else 100
        if hp_pct > 80:
            health_desc = "状态良好"
        elif hp_pct > 50:
            health_desc = "有些伤痕"
        elif hp_pct > 25:
            health_desc = "伤势不轻"
        else:
            health_desc = "奄奄一息"

        fatigue_desc = ("精力充沛" if fatigue < 30 else
                        "有些疲惫" if fatigue < 60 else
                        "非常疲倦" if fatigue < 85 else
                        "筋疲力尽")

        inv_str = "、".join(inventory[:10]) if inventory else "无"
        quest_str = "、".join(quest_flags.keys()) if quest_flags else "无"

        return (
            f"## 当前世界状态\n"
            f"- 玩家角色：{char_name}（{char_class}）\n"
            f"- 当前位置：{location}\n"
            f"- 当前状态：{status_names.get(status, '探索中')}\n"
            f"- 生命值：{hp}/{max_hp}（{health_desc}）\n"
            f"- 疲劳度：{fatigue}/100（{fatigue_desc}）\n"
            f"- 金币：{gold}\n"
            f"- 背包：{inv_str}\n"
            f"- 任务线索：{quest_str}\n"
            f"- 回合：{turn} · 第{chapter}章\n"
            f"\n角色当前{health_desc}且{fatigue_desc}，叙事应反映这一身体状况。"
            + (f"\n⚠ 角色生命垂危（HP≤25%），叙事应传达强烈的紧张感和求生意志。"
               if hp_pct <= 25 else "")
        )
