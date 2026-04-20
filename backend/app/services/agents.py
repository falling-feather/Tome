"""
多智能体编排与审计系统 (M5)

四个专职代理 + 一个编排器:
- CharacterAgent:  角色一致性守卫
- WorldAgent:      世界观一致性守卫
- NarrativeAgent:  叙事质量代理
- AuditAgent:      最终审计代理
- AgentOrchestrator: 总编排器，仲裁与合成
"""
import re
import logging
from dataclasses import dataclass, field
from typing import Optional, Callable, Awaitable

from backend.app.config import settings

logger = logging.getLogger("inkless")


# ---------------------------------------------------------------------------
# 代理审查结果
# ---------------------------------------------------------------------------
@dataclass
class AgentVerdict:
    """单个代理的审查结果"""
    agent_name: str
    passed: bool
    issues: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)
    rewrite: str = ""  # 建议重写文本（仅 AuditAgent 可填）


@dataclass
class OrchestratorResult:
    """编排器最终结果"""
    final_text: str
    was_rewritten: bool = False
    verdicts: list[AgentVerdict] = field(default_factory=list)
    total_issues: int = 0


# ---------------------------------------------------------------------------
# 角色一致性代理
# ---------------------------------------------------------------------------
class CharacterAgent:
    """检查 AI 输出是否与角色设定一致"""

    # 角色职业 → 不应出现的能力/行为关键词
    CLASS_RESTRICTIONS = {
        "剑客": ["魔法", "咒语", "施法", "法术", "黑客", "编程"],
        "法师": ["拔剑", "挥刀", "剑法", "刀法", "枪械"],
        "盗贼": ["正面冲锋", "重甲", "圣光", "神术"],
        "战士": ["隐身", "魔法", "咒语", "施法"],
        "黑客": ["挥剑", "魔法", "法术", "内力"],
        "武僧": ["枪械", "黑客", "编程", "魔法"],
    }

    # 场景 → 不应出现的元素
    SCENARIO_RESTRICTIONS = {
        "fantasy": ["手机", "电脑", "网络", "汽车", "飞机", "激光"],
        "scifi": ["魔法", "咒语", "法术", "内力", "灵力", "仙术"],
        "wuxia": ["魔法", "激光", "电脑", "手机", "外星", "机器人"],
    }

    def check(self, text: str, state: dict) -> AgentVerdict:
        verdict = AgentVerdict(agent_name="CharacterAgent", passed=True)
        char_class = state.get("character_class", "")
        scenario = state.get("scenario", "fantasy")
        char_name = state.get("character_name", "")

        # 检查职业限制
        restrictions = self.CLASS_RESTRICTIONS.get(char_class, [])
        for keyword in restrictions:
            if keyword in text:
                verdict.passed = False
                verdict.issues.append(f"角色职业[{char_class}]不应使用[{keyword}]")
                verdict.suggestions.append(f"移除或替换与职业不符的[{keyword}]描写")

        # 检查场景一致性
        scene_restrictions = self.SCENARIO_RESTRICTIONS.get(scenario, [])
        for keyword in scene_restrictions:
            if keyword in text:
                verdict.passed = False
                verdict.issues.append(f"[{scenario}]场景不应出现[{keyword}]")

        # 检查角色名是否被正确使用（不应把玩家称为其他名字）
        wrong_names = ["勇者", "英雄", "冒险者"]
        if char_name and char_name not in ["旅行者", "冒险者"]:
            for wrong in wrong_names:
                # 只在直接称呼的上下文中检查
                if f"你是{wrong}" in text or f"叫你{wrong}" in text:
                    verdict.issues.append(f"角色名为[{char_name}]，不应被称为[{wrong}]")

        return verdict


# ---------------------------------------------------------------------------
# 世界观一致性代理
# ---------------------------------------------------------------------------
class WorldAgent:
    """检查 AI 输出是否与世界观设定一致"""

    # 死亡状态下不应出现的内容
    DEAD_RESTRICTIONS = ["攻击", "奔跑", "跳跃", "施法", "战斗", "交易"]

    # 地点相关关键词矛盾检查
    LOCATION_KEYWORDS = {
        "客栈": ["海浪", "沙漠", "太空", "丛林"],
        "森林": ["海水", "船只", "码头", "太空"],
        "城镇": ["荒野猛兽", "原始丛林", "深海"],
        "荒野": ["店铺", "酒馆", "旅店"],
    }

    def check(self, text: str, state: dict) -> AgentVerdict:
        verdict = AgentVerdict(agent_name="WorldAgent", passed=True)
        status = state.get("status", "exploring")
        location = state.get("current_location", "")

        # 死亡状态检查
        if status == "dead":
            for kw in self.DEAD_RESTRICTIONS:
                if kw in text:
                    verdict.passed = False
                    verdict.issues.append(f"角色已死亡，不应出现[{kw}]行为")

        # 地点一致性
        for loc, bad_keywords in self.LOCATION_KEYWORDS.items():
            if loc in location:
                for kw in bad_keywords:
                    if kw in text:
                        verdict.issues.append(f"当前在[{location}]，[{kw}]可能与场景不符")

        # HP 一致性：奄奄一息不应描写生龙活虎
        hp = state.get("health", 100)
        max_hp = state.get("max_health", 100)
        if max_hp > 0 and hp / max_hp < 0.2:
            vigor_words = ["精力充沛", "龙精虎猛", "生龙活虎", "活力四射"]
            for w in vigor_words:
                if w in text:
                    verdict.issues.append(f"HP仅{hp}/{max_hp}，不应描述为[{w}]")

        # 疲劳一致性
        fatigue = state.get("fatigue", 0)
        if fatigue > 80:
            energy_words = ["精神抖擞", "毫不疲倦", "充满活力"]
            for w in energy_words:
                if w in text:
                    verdict.issues.append(f"疲劳度{fatigue}，不应描述为[{w}]")

        return verdict


# ---------------------------------------------------------------------------
# 叙事质量代理
# ---------------------------------------------------------------------------
class NarrativeAgent:
    """检查叙事质量：视角、长度、可读性"""

    # 不应出现的第一人称（AI 视角泄露）
    AI_LEAKS = [
        "作为AI", "作为一个AI", "作为人工智能", "我是AI",
        "我无法", "我不能", "根据我的设定", "我的训练数据",
        "让我来为你", "以下是", "好的，我来",
    ]

    # 过度使用的叙事套路
    CLICHÉS = [
        "一切都变了", "命运的齿轮", "殊不知", "却不知道",
        "只见", "但见",  # 多次出现才算问题
    ]

    def check(self, text: str, state: dict) -> AgentVerdict:
        verdict = AgentVerdict(agent_name="NarrativeAgent", passed=True)

        # 检测 AI 身份泄露
        for leak in self.AI_LEAKS:
            if leak in text:
                verdict.passed = False
                verdict.issues.append(f"检测到AI身份泄露: [{leak}]")

        # 检查长度
        if len(text) < 50:
            verdict.issues.append("回复过短（<50字），叙事可能不够丰满")
        elif len(text) > 1000:
            verdict.issues.append("回复过长（>1000字），可能需要精简")

        # 检查是否有第二人称叙事（期望）
        if "你" not in text and len(text) > 100:
            verdict.issues.append("叙事缺少第二人称'你'，可能视角不对")

        # 套路检测（同一套路出现多次）
        for cliché in self.CLICHÉS:
            count = text.count(cliché)
            if count >= 2:
                verdict.issues.append(f"[{cliché}]重复使用{count}次，建议变换表达")

        # Markdown/代码块泄露检查
        if "```" in text or "##" in text:
            verdict.issues.append("检测到Markdown格式泄露，应为纯叙事文本")

        return verdict


# ---------------------------------------------------------------------------
# 审计代理
# ---------------------------------------------------------------------------
class AuditAgent:
    """最终审计：综合所有代理结果，决定是否需要修正"""

    # 严重问题模式 — 必须修正
    CRITICAL_PATTERNS = [
        (r"作为AI", ""),
        (r"作为一个AI", ""),
        (r"作为人工智能", ""),
        (r"我是AI", ""),
        (r"```[\s\S]*?```", ""),  # 代码块
        (r"^#{1,6}\s", ""),       # Markdown 标题
    ]

    def audit(self, text: str, verdicts: list[AgentVerdict], state: dict) -> AgentVerdict:
        """
        综合审计：汇总所有代理意见，执行必要的文本修正。
        """
        result = AgentVerdict(agent_name="AuditAgent", passed=True)
        all_issues = []

        for v in verdicts:
            all_issues.extend(v.issues)

        critical_count = sum(1 for v in verdicts if not v.passed)

        if critical_count > 0:
            result.passed = False
            result.issues.append(f"{critical_count}个代理报告严重问题")

        # 尝试自动修正关键问题
        fixed_text = text
        was_fixed = False

        for pattern, replacement in self.CRITICAL_PATTERNS:
            new_text = re.sub(pattern, replacement, fixed_text, flags=re.MULTILINE)
            if new_text != fixed_text:
                was_fixed = True
                fixed_text = new_text

        # 如果有修正，清理多余空行
        if was_fixed:
            fixed_text = re.sub(r"\n{3,}", "\n\n", fixed_text).strip()
            result.rewrite = fixed_text
            result.suggestions.append("已自动修正关键格式/身份泄露问题")

        # 如果问题过多(>=5)，建议降级到安全模板
        if len(all_issues) >= 5:
            result.suggestions.append("问题过多，建议使用降级模板重新生成")

        result.issues.extend(all_issues[:10])  # 最多保留10条
        return result


# ---------------------------------------------------------------------------
# 编排器
# ---------------------------------------------------------------------------
class AgentOrchestrator:
    """
    多智能体编排器：协调各代理检查并合成最终结果。

    流程:
    1. CharacterAgent 检查角色一致性
    2. WorldAgent 检查世界观一致性
    3. NarrativeAgent 检查叙事质量
    4. AuditAgent 综合审计 + 必要修正
    5. 如果审计建议降级且提供了 llm_complete，使用 LLM 重写
    """

    # 降级模板 — 当所有修正都无法挽回时使用
    FALLBACK_TEMPLATES = {
        "exploring": "你继续在{location}中探索。四周的景色依旧，但你隐约感到有什么变化正在酝酿。你谨慎地环顾四周，思考着下一步该做什么。",
        "combat": "战斗仍在继续。你紧握武器，警惕地注视着对手的一举一动。局势依然胶着，你需要做出下一个决定。",
        "resting": "你在{location}找了一个安静的角落休息。疲惫的身体逐渐恢复，但你知道冒险还远未结束。",
        "trading": "你仔细端详着眼前的商品，思考着哪些值得购买。商人耐心地等待着你的决定。",
        "dialogue": "对话还在继续。对方注视着你，等待你的回应。你需要慎重考虑接下来要说什么。",
        "dead": "一切归于沉寂。你的冒险在这里画上了句号……但或许，这并非终点。",
    }

    def __init__(self):
        self.character_agent = CharacterAgent()
        self.world_agent = WorldAgent()
        self.narrative_agent = NarrativeAgent()
        self.audit_agent = AuditAgent()

    async def process(
        self,
        text: str,
        state: dict,
        llm_complete: Optional[Callable[[str, int], Awaitable[str]]] = None,
    ) -> OrchestratorResult:
        """
        对 AI 生成的文本进行多代理审查和修正。
        """
        # 1. 各代理并行检查
        verdicts = [
            self.character_agent.check(text, state),
            self.world_agent.check(text, state),
            self.narrative_agent.check(text, state),
        ]

        # 2. 审计代理汇总
        audit_verdict = self.audit_agent.audit(text, verdicts, state)
        verdicts.append(audit_verdict)

        total_issues = sum(len(v.issues) for v in verdicts)

        # 3. 决定最终文本
        final_text = text

        if audit_verdict.rewrite:
            # 审计代理有自动修正
            final_text = audit_verdict.rewrite

        # 4. 如果问题 >= 阈值且有 LLM，尝试重写
        rewrite_threshold = settings.AUDIT_REWRITE_THRESHOLD
        fallback_threshold = int(rewrite_threshold * 1.6)
        was_rewritten = False
        if total_issues >= rewrite_threshold and llm_complete:
            try:
                rewrite_prompt = self._build_rewrite_prompt(text, verdicts, state)
                rewritten = await llm_complete(rewrite_prompt, 512)
                if rewritten and len(rewritten) > 50:
                    final_text = rewritten
                    was_rewritten = True
                    logger.info(f"审计代理触发LLM重写, 修正{total_issues}个问题")
            except Exception as e:
                logger.warning(f"LLM重写失败: {e}")

        # 5. 如果重写也失败且严重问题过多，使用降级模板
        if total_issues >= fallback_threshold and not was_rewritten:
            status = state.get("status", "exploring")
            location = state.get("current_location", "未知之地")
            template = self.FALLBACK_TEMPLATES.get(status, self.FALLBACK_TEMPLATES["exploring"])
            final_text = template.format(location=location)
            was_rewritten = True
            logger.warning(f"审计降级: 使用安全模板替代, 原始问题数={total_issues}")

        return OrchestratorResult(
            final_text=final_text,
            was_rewritten=was_rewritten,
            verdicts=verdicts,
            total_issues=total_issues,
        )

    def _build_rewrite_prompt(self, text: str, verdicts: list[AgentVerdict], state: dict) -> str:
        """构建重写提示词"""
        issues_text = "\n".join(
            f"- {issue}"
            for v in verdicts
            for issue in v.issues[:3]
        )

        char_name = state.get("character_name", "旅行者")
        char_class = state.get("character_class", "冒险者")
        scenario = state.get("scenario", "fantasy")

        return (
            f"以下游戏叙事文本存在问题，请修正后输出纯叙事文本。\n"
            f"角色: {char_name}（{char_class}），场景类型: {scenario}\n"
            f"发现的问题:\n{issues_text}\n\n"
            f"原文:\n{text[:800]}\n\n"
            f"请输出修正后的文本（200-400字，第二人称视角，纯叙事，无Markdown）："
        )
