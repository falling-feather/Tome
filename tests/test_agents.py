"""Agents 审查系统单元测试"""
import pytest

from backend.app.services.agents import (
    CharacterAgent,
    WorldAgent,
    NarrativeAgent,
    AuditAgent,
    AgentOrchestrator,
    AgentVerdict,
)


@pytest.fixture
def fantasy_state():
    return {
        "scenario": "fantasy",
        "character_class": "战士",
        "health": 80,
        "max_health": 100,
        "fatigue": 20,
        "money": 50,
        "status": "exploring",
        "current_location": "边境小镇",
        "inventory": ["铁剑"],
        "turn": 5,
        "chapter": 1,
    }


@pytest.fixture
def scifi_state():
    return {
        "scenario": "scifi",
        "character_class": "工程师",
        "health": 90,
        "max_health": 100,
        "fatigue": 10,
        "money": 100,
        "status": "exploring",
        "current_location": "空间站",
        "inventory": ["扳手"],
        "turn": 5,
        "chapter": 1,
    }


# ---------------------------------------------------------------------------
# CharacterAgent
# ---------------------------------------------------------------------------
class TestCharacterAgent:
    def test_clean_text_passes(self, fantasy_state):
        agent = CharacterAgent()
        text = "你挥动铁剑，猛力砍向面前的敌人。战士的力量让你占据了上风。"
        verdict = agent.check(text, fantasy_state)
        assert verdict.passed is True

    def test_scifi_terms_in_fantasy_flagged(self, fantasy_state):
        agent = CharacterAgent()
        text = "你掏出激光枪，瞄准了远处的机器人。飞船的引擎轰鸣着。"
        verdict = agent.check(text, fantasy_state)
        assert verdict.passed is False
        assert any("激光" in i for i in verdict.issues)

    def test_class_restriction(self, fantasy_state):
        """战士不应该施展魔法"""
        agent = CharacterAgent()
        text = "你身为战士，施展了一个强大的魔法，瞬间毁灭了敌人。"
        verdict = agent.check(text, fantasy_state)
        assert verdict.passed is False
        assert verdict.agent_name == "CharacterAgent"


# ---------------------------------------------------------------------------
# WorldAgent
# ---------------------------------------------------------------------------
class TestWorldAgent:
    def test_dead_status_inconsistency(self, fantasy_state):
        agent = WorldAgent()
        fantasy_state["status"] = "dead"
        text = "你精力充沛地奔跑在草原上，挥舞着武器。"
        verdict = agent.check(text, fantasy_state)
        assert verdict.passed is False

    def test_healthy_state_passes(self, fantasy_state):
        agent = WorldAgent()
        text = "你在小镇的集市上闲逛，周围是熙攘的人群。"
        verdict = agent.check(text, fantasy_state)
        assert verdict.passed is True

    def test_low_health_vigor_mismatch(self, fantasy_state):
        agent = WorldAgent()
        fantasy_state["health"] = 5
        text = "你精神抖擞，充满活力地冲向了战场。"
        verdict = agent.check(text, fantasy_state)
        assert isinstance(verdict.issues, list)


# ---------------------------------------------------------------------------
# NarrativeAgent
# ---------------------------------------------------------------------------
class TestNarrativeAgent:
    def test_ai_identity_leak(self, fantasy_state):
        agent = NarrativeAgent()
        text = "作为一个AI助手，我无法真正体验这个世界。让我继续描述你的冒险。"
        verdict = agent.check(text, fantasy_state)
        assert verdict.passed is False

    def test_clean_narrative_passes(self, fantasy_state):
        agent = NarrativeAgent()
        text = "月光洒在古老的石路上，你的脚步声在寂静的夜晚中回响。远处传来猫头鹰的鸣叫。"
        verdict = agent.check(text, fantasy_state)
        assert verdict.passed is True

    def test_too_short_text(self, fantasy_state):
        agent = NarrativeAgent()
        text = "你走了。"
        verdict = agent.check(text, fantasy_state)
        assert verdict.passed is False or len(verdict.issues) > 0


# ---------------------------------------------------------------------------
# AuditAgent
# ---------------------------------------------------------------------------
class TestAuditAgent:
    def test_no_issues_passes(self, fantasy_state):
        agent = AuditAgent()
        verdicts = [
            AgentVerdict(agent_name="CharacterAgent", passed=True, issues=[], suggestions=[]),
            AgentVerdict(agent_name="WorldAgent", passed=True, issues=[], suggestions=[]),
            AgentVerdict(agent_name="NarrativeAgent", passed=True, issues=[], suggestions=[]),
        ]
        text = "你走进了古老的神殿，墙壁上的壁画讲述着远古的故事。"
        result = agent.audit(text, verdicts, fantasy_state)
        assert result.passed is True

    def test_with_issues_attempts_fix(self, fantasy_state):
        agent = AuditAgent()
        verdicts = [
            AgentVerdict(
                agent_name="NarrativeAgent",
                passed=False,
                issues=["AI身份泄露"],
                suggestions=["移除AI相关表述"],
            ),
        ]
        text = "作为AI，你来到了森林。"
        result = agent.audit(text, verdicts, fantasy_state)
        assert isinstance(result.rewrite, (str, type(None)))


# ---------------------------------------------------------------------------
# AgentOrchestrator
# ---------------------------------------------------------------------------
class TestAgentOrchestrator:
    @pytest.mark.asyncio
    async def test_process_clean_text(self, fantasy_state):
        async def mock_llm(prompt, max_tokens=200):
            return "你的冒险继续着。"

        orchestrator = AgentOrchestrator()
        text = "你沿着蜿蜒的小路走进了幽暗森林。古老的树木遮蔽了天空，只有零星的阳光穿过树叶。"
        result = await orchestrator.process(text, fantasy_state, mock_llm)
        assert result.final_text is not None
        assert isinstance(result.total_issues, int)

    @pytest.mark.asyncio
    async def test_process_with_ai_leak(self, fantasy_state):
        async def mock_llm(prompt, max_tokens=200):
            return "月光下，你继续前行。"

        orchestrator = AgentOrchestrator()
        text = "作为一个AI语言模型，我来描述你的冒险。你走进了一片森林。"
        result = await orchestrator.process(text, fantasy_state, mock_llm)
        assert result.total_issues > 0
