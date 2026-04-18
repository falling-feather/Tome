"""
输出后处理管道 — 解析 AI 响应, 提取结构化信息, 格式校验
"""
import re
import logging

logger = logging.getLogger("inkless")


class ResponsePostProcessor:
    """
    对 LLM 的响应进行后处理:
    1. 格式修复 (移除不当内容)
    2. 结构化信息提取 (物品、NPC、位置)
    3. 一致性检查
    """

    # 需要移除的元叙事模式
    META_PATTERNS = [
        r'作为一个?AI',
        r'作为语言模型',
        r'我无法',
        r'在这个游戏中',
        r'游戏设定',
        r'根据游戏规则',
        r'\[OOC\]',
        r'\(out of character\)',
    ]

    # "你可以..." 建议列表清除模式
    SUGGEST_PATTERNS = [
        # "你可以：" / "**你可以：**" 及后续列表行
        r'(?:\*{0,2})你可以(?:选择)?(?:：|:)(?:\*{0,2})\s*(?:\n[•\-\*\d].*)*',
        # 行首的 "你可以..." 引导句
        r'\n\s*你可以[：:]?\s*\n(?:\s*[•\-\*\d].*\n?)+',
        # 单行 "你可以选择……" 句
        r'你可以选择(?:：|:).*$',
    ]

    # Markdown 格式清除
    MD_PATTERNS = [
        (r'\*\*(.+?)\*\*', r'\1'),    # **bold** → bold
        (r'\*(.+?)\*', r'\1'),         # *italic* → italic
        (r'^#{1,6}\s+', ''),           # # heading → heading
        (r'`(.+?)`', r'\1'),           # `code` → code
    ]

    # 物品关键词提取模式
    ITEM_ACQUIRE_PATTERNS = [
        r'(?:获得|得到|捡起|拿到|收获|拾取|入手)(?:了)?[「『【]?(.{2,10})[」』】]?',
        r'[「『【](.{2,10})[」』】](?:到手|入囊|归你)',
    ]

    ITEM_LOSE_PATTERNS = [
        r'(?:丢失|失去|交出|给出|消耗|使用)(?:了)?[「『【]?(.{2,10})[」』】]?',
    ]

    # NPC 名称提取模式
    NPC_NAME_PATTERNS = [
        r'(?:一位|一个|一名)(?:叫|名叫|自称)?[「『【]?([^\s「『【」』】]{2,6})[」』】]?',
        r'[「『【]([^\s」』】]{2,6})[」』】](?:说|道|笑|叹|怒|喝)',
    ]

    # 金币变动提取
    MONEY_PATTERNS = [
        r'(?:支付|花费|消费)(?:了)?(\d+)',
        r'(?:获得|得到|赚取)(?:了)?(\d+)(?:枚)?(?:金币|银两|信用点)',
    ]

    # 对话分段标记模式
    SEGMENT_TAG_RE = re.compile(
        r'^\[(?:旁白|角色[:：](.+?))\]\s*$',
        re.MULTILINE,
    )

    def process(self, text: str, state: dict) -> dict:
        """
        处理 AI 响应文本, 返回后处理结果.

        Returns:
            {
                "cleaned_text": str,        # 清理后的文本
                "extracted": {
                    "items_gained": list,   # 获得的物品
                    "items_lost": list,     # 失去的物品
                    "npcs_mentioned": list, # 提到的 NPC
                    "money_spent": int,     # 花费的金币
                    "money_gained": int,    # 获得的金币
                },
                "warnings": list,           # 格式/一致性警告
            }
        """
        warnings = []
        cleaned = text

        # 1. 移除元叙事
        for pattern in self.META_PATTERNS:
            matches = re.findall(pattern, cleaned, re.IGNORECASE)
            if matches:
                cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE)
                warnings.append(f"已移除元叙事内容: {pattern}")

        # 2. 修复格式问题
        cleaned = self._fix_formatting(cleaned)

        # 3. 提取结构化信息
        extracted = self._extract_info(cleaned, state)

        # 4. 一致性检查
        consistency_warnings = self._check_consistency(cleaned, state)
        warnings.extend(consistency_warnings)

        # 5. 长度检查
        if len(cleaned) < 50:
            warnings.append("回复过短(< 50字)")
        elif len(cleaned) > 1000:
            warnings.append("回复过长(> 1000字)")

        result = {
            "cleaned_text": cleaned.strip(),
            "extracted": extracted,
            "warnings": warnings,
            "segments": self.parse_dialogue_segments(cleaned.strip()),
        }

        if warnings:
            logger.debug(f"后处理警告: {warnings}")

        return result

    def _fix_formatting(self, text: str) -> str:
        """修复常见格式问题"""
        # 移除 "你可以..." 建议块
        for pattern in self.SUGGEST_PATTERNS:
            text = re.sub(pattern, '', text, flags=re.MULTILINE)

        # 清除 Markdown 格式标记
        for pattern, replacement in self.MD_PATTERNS:
            text = re.sub(pattern, replacement, text, flags=re.MULTILINE)

        # 移除多余空行
        text = re.sub(r'\n{3,}', '\n\n', text)

        # 移除首尾无意义的引号/括号
        text = re.sub(r'^[「『【]+\s*', '', text)

        # 修复破损的标点
        text = re.sub(r'。{2,}', '。', text)
        text = re.sub(r'！{3,}', '！！', text)
        text = re.sub(r'？{3,}', '？？', text)

        return text

    def _extract_info(self, text: str, state: dict) -> dict:
        """从文本中提取结构化信息"""
        items_gained = []
        items_lost = []
        npcs_mentioned = []
        money_spent = 0
        money_gained = 0

        # 物品获取
        for pattern in self.ITEM_ACQUIRE_PATTERNS:
            matches = re.findall(pattern, text)
            items_gained.extend(m.strip() for m in matches if m.strip())

        # 物品失去
        for pattern in self.ITEM_LOSE_PATTERNS:
            matches = re.findall(pattern, text)
            items_lost.extend(m.strip() for m in matches if m.strip())

        # NPC 名称
        for pattern in self.NPC_NAME_PATTERNS:
            matches = re.findall(pattern, text)
            for m in matches:
                name = m.strip()
                # 过滤掉常见非NPC词
                skip_words = {"一些", "这里", "那边", "一个", "什么", "东西", "地方"}
                if name not in skip_words and len(name) >= 2:
                    npcs_mentioned.append(name)

        # 金币变动
        for pattern in self.MONEY_PATTERNS:
            matches = re.findall(pattern, text)
            for m in matches:
                try:
                    val = int(m)
                    if "支付" in text or "花费" in text or "消费" in text:
                        money_spent += val
                    else:
                        money_gained += val
                except ValueError:
                    pass

        # 去重
        items_gained = list(dict.fromkeys(items_gained))
        items_lost = list(dict.fromkeys(items_lost))
        npcs_mentioned = list(dict.fromkeys(npcs_mentioned))

        return {
            "items_gained": items_gained[:5],
            "items_lost": items_lost[:5],
            "npcs_mentioned": npcs_mentioned[:5],
            "money_spent": money_spent,
            "money_gained": money_gained,
        }

    def _check_consistency(self, text: str, state: dict) -> list[str]:
        """一致性检查"""
        warnings = []

        char_name = state.get("character_name", "旅行者")

        # 检查是否包含角色自称的矛盾 (如第一人称)
        first_person = re.findall(r'(?:^|[。！？\n])我(?:是|要|会|可以|想|决定)', text)
        if len(first_person) > 2:
            warnings.append("叙事视角可能不一致(过多第一人称)")

        # 检查是否出现不在当前场景的元素
        scenario = state.get("scenario", "fantasy")
        if scenario == "fantasy":
            sci_words = ["飞船", "量子", "激光", "机器人", "太空", "星球"]
            for w in sci_words:
                if w in text:
                    warnings.append(f"奇幻场景中出现科幻元素: {w}")
                    break
        elif scenario == "scifi":
            wuxia_words = ["内力", "穴道", "武功秘籍", "轻功", "江湖"]
            for w in wuxia_words:
                if w in text:
                    warnings.append(f"科幻场景中出现武侠元素: {w}")
                    break
        elif scenario == "wuxia":
            sci_words = ["飞船", "机器人", "太空", "激光", "量子"]
            for w in sci_words:
                if w in text:
                    warnings.append(f"武侠场景中出现科幻元素: {w}")
                    break

        return warnings

    # ------------------------------------------------------------------
    # 多角色对话分段解析
    # ------------------------------------------------------------------
    def parse_dialogue_segments(self, text: str) -> list[dict]:
        """
        解析带 [旁白] / [角色:XXX] 标记的文本，返回分段列表。
        每个分段: {"speaker": "narrator" | 角色名, "content": str}
        若文本不含标记则整段视为旁白。
        """
        lines = text.split('\n')
        segments: list[dict] = []
        current_speaker = "narrator"
        current_lines: list[str] = []

        for line in lines:
            m = self.SEGMENT_TAG_RE.match(line.strip())
            if m:
                # 保存前一段
                content = '\n'.join(current_lines).strip()
                if content:
                    segments.append({"speaker": current_speaker, "content": content})
                # 切换说话者
                char_name = m.group(1)
                current_speaker = char_name.strip() if char_name else "narrator"
                current_lines = []
            else:
                current_lines.append(line)

        # 保存最后一段
        content = '\n'.join(current_lines).strip()
        if content:
            segments.append({"speaker": current_speaker, "content": content})

        # 若没有任何标记，整段视为旁白
        if not segments:
            segments.append({"speaker": "narrator", "content": text.strip()})

        return segments
