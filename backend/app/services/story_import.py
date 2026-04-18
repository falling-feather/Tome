"""
自编故事导入服务 — 使用 LLM 解析用户导入的故事/小说内容，
提取角色、地点、世界规则、剧情摘要等结构化数据。
"""
import json
import logging
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models import CustomStory, WorldEntry

logger = logging.getLogger("inkless")

# 用于限制输入长度 (避免超长文本耗尽 token)
MAX_RAW_CHARS = 15000

PARSE_PROMPT = """你是一个专业的故事分析系统。请仔细阅读以下故事/小说内容，提取结构化信息。

【故事内容】
{content}

请严格按以下 JSON 格式返回（不要添加任何其他文字）：
{{
  "title_suggest": "建议的故事标题（如果输入没有明确标题）",
  "plot_summary": "故事主要剧情的简短概述（100字以内）",
  "world_rules": "这个故事世界的基本规则/设定（如魔法体系、科技水平等，80字以内）",
  "opening_scene": "适合作为互动冒险开场的场景描述（80字以内）",
  "characters": [
    {{
      "name": "角色名",
      "description": "外貌和身份描述（30字以内）",
      "personality": "性格特点（20字以内）",
      "speaking_style": "说话风格简述（20字以内）"
    }}
  ],
  "locations": [
    {{
      "name": "地点名",
      "description": "地点描述（30字以内）"
    }}
  ]
}}

要求：
- characters 最多提取 8 个主要角色
- locations 最多提取 6 个关键地点
- 所有描述要简洁有力
- 必须返回合法 JSON"""


class StoryImportService:

    def __init__(self, db: AsyncSession):
        self.db = db

    async def parse_story(self, story: CustomStory, llm_complete) -> None:
        """
        使用 LLM 解析故事内容，填充 parsed_data 字段。
        llm_complete: async callable(prompt, max_tokens) -> str
        """
        story.status = "parsing"
        await self.db.commit()

        try:
            # 截断过长内容
            raw = story.raw_content
            if len(raw) > MAX_RAW_CHARS:
                raw = raw[:MAX_RAW_CHARS] + "\n\n[内容已截断...]"

            prompt = PARSE_PROMPT.format(content=raw)
            result_text = await llm_complete(prompt, max_tokens=1024)

            # 尝试从回复中提取 JSON
            parsed = self._extract_json(result_text)
            if not parsed:
                raise ValueError("LLM 返回的内容无法解析为 JSON")

            # 校验必要字段
            if "characters" not in parsed or "locations" not in parsed:
                raise ValueError("缺少 characters 或 locations 字段")

            story.parsed_data = parsed
            story.status = "ready"

            # 如果标题为空，使用建议标题
            if story.title == "未命名故事" and parsed.get("title_suggest"):
                story.title = parsed["title_suggest"][:64]

            await self.db.commit()
            logger.info(f"故事 #{story.id} 解析完成: {len(parsed.get('characters', []))} 角色, {len(parsed.get('locations', []))} 地点")

        except Exception as e:
            story.status = "error"
            story.error_msg = str(e)[:500]
            await self.db.commit()
            logger.error(f"故事 #{story.id} 解析失败: {e}")
            raise

    def _extract_json(self, text: str) -> dict | None:
        """从 LLM 回复中提取 JSON 对象"""
        # 尝试直接解析
        text = text.strip()
        if text.startswith('{'):
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                pass

        # 尝试找 ```json ... ``` 块
        import re
        m = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(1))
            except json.JSONDecodeError:
                pass

        # 尝试找第一个 { 到最后一个 }
        start = text.find('{')
        end = text.rfind('}')
        if start >= 0 and end > start:
            try:
                return json.loads(text[start:end + 1])
            except json.JSONDecodeError:
                pass

        return None

    async def create_world_entries(self, story: CustomStory) -> int:
        """
        将解析后的故事数据写入世界书条目，供游戏引擎使用。
        返回创建的条目数量。
        """
        parsed = story.parsed_data or {}
        scenario = f"custom_{story.id}"
        count = 0

        # 世界规则
        if parsed.get("world_rules"):
            self.db.add(WorldEntry(
                scenario=scenario, layer="core", category="rule",
                title=f"[{story.title}] 世界规则",
                keywords=story.title,
                content=parsed["world_rules"],
                priority=10, is_active=True,
            ))
            count += 1

        # 剧情概述
        if parsed.get("plot_summary"):
            self.db.add(WorldEntry(
                scenario=scenario, layer="core", category="lore",
                title=f"[{story.title}] 剧情概述",
                keywords=story.title,
                content=parsed["plot_summary"],
                priority=9, is_active=True,
            ))
            count += 1

        # 角色
        for char in parsed.get("characters", [])[:8]:
            name = char.get("name", "未知")
            desc = char.get("description", "")
            personality = char.get("personality", "")
            style = char.get("speaking_style", "")
            content = f"{desc}。性格：{personality}。说话风格：{style}"
            keywords = f"{story.title},{name}"
            self.db.add(WorldEntry(
                scenario=scenario, layer="core", category="character",
                title=f"[{story.title}] {name}",
                keywords=keywords,
                content=content,
                priority=8, is_active=True,
            ))
            count += 1

        # 地点
        for loc in parsed.get("locations", [])[:6]:
            name = loc.get("name", "未知")
            desc = loc.get("description", "")
            keywords = f"{story.title},{name}"
            self.db.add(WorldEntry(
                scenario=scenario, layer="core", category="location",
                title=f"[{story.title}] {name}",
                keywords=keywords,
                content=desc,
                priority=7, is_active=True,
            ))
            count += 1

        await self.db.commit()
        logger.info(f"故事 #{story.id} 创建了 {count} 条世界书条目")
        return count
