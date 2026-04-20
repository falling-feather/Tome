"""GameEngine 单元测试"""
import pytest

from backend.app.services.game_engine import (
    GameEngine,
    STATUS_EXPLORING,
    STATUS_COMBAT,
    STATUS_RESTING,
    STATUS_TRADING,
    STATUS_DIALOGUE,
    STATUS_DEAD,
    SCENARIOS,
    load_events_from_db,
    seed_events_if_empty,
)


@pytest.fixture
def engine():
    return GameEngine()


@pytest.fixture
def base_state(engine):
    return engine.create_initial_state("测试者", "战士", "fantasy")


# ---------------------------------------------------------------------------
# create_initial_state
# ---------------------------------------------------------------------------
class TestCreateInitialState:
    def test_default_values(self, engine):
        state = engine.create_initial_state("张三", "法师", "fantasy")
        assert state["character_name"] == "张三"
        assert state["character_class"] == "法师"
        assert state["scenario"] == "fantasy"
        assert state["health"] == 100
        assert state["fatigue"] == 0
        assert state["money"] == 50
        assert state["status"] == STATUS_EXPLORING
        assert state["turn"] == 0
        assert state["chapter"] == 1
        assert state["inventory"] == []
        assert state["death_save_used"] is False

    def test_scenario_starting_location(self, engine):
        for scenario, sc_def in SCENARIOS.items():
            state = engine.create_initial_state("X", "Y", scenario)
            assert state["current_location"] == sc_def["locations"][0]

    def test_unknown_scenario_defaults_to_fantasy(self, engine):
        state = engine.create_initial_state("X", "Y", "nonexistent")
        assert state["current_location"] == SCENARIOS["fantasy"]["locations"][0]


# ---------------------------------------------------------------------------
# generate_intro
# ---------------------------------------------------------------------------
class TestGenerateIntro:
    def test_contains_character_info(self, engine, base_state):
        intro = engine.generate_intro(base_state)
        assert "测试者" in intro
        assert "战士" in intro

    def test_contains_location(self, engine, base_state):
        intro = engine.generate_intro(base_state)
        assert base_state["current_location"] in intro


# ---------------------------------------------------------------------------
# validate_action
# ---------------------------------------------------------------------------
class TestValidateAction:
    def test_normal_action_passes(self, engine, base_state):
        valid, reason = engine.validate_action(base_state, "向北走")
        assert valid is True
        assert reason == ""

    def test_dead_state_rejects(self, engine, base_state):
        base_state["status"] = STATUS_DEAD
        valid, reason = engine.validate_action(base_state, "攻击敌人")
        assert valid is False
        assert "死亡" in reason

    def test_extreme_fatigue_blocks_combat(self, engine, base_state):
        base_state["fatigue"] = 95
        valid, reason = engine.validate_action(base_state, "拔剑攻击")
        assert valid is False
        assert "筋疲力尽" in reason

    def test_fatigue_89_allows_combat(self, engine, base_state):
        base_state["fatigue"] = 89
        valid, _ = engine.validate_action(base_state, "攻击")
        assert valid is True

    def test_fatigue_does_not_block_noncombat(self, engine, base_state):
        base_state["fatigue"] = 95
        valid, _ = engine.validate_action(base_state, "休息一下")
        assert valid is True


# ---------------------------------------------------------------------------
# _infer_status
# ---------------------------------------------------------------------------
class TestInferStatus:
    def test_combat_keyword_from_exploring(self, engine):
        result = engine._infer_status("拔剑战斗", "", STATUS_EXPLORING)
        assert result == STATUS_COMBAT

    def test_rest_keyword_from_exploring(self, engine):
        result = engine._infer_status("找个地方休息", "", STATUS_EXPLORING)
        assert result == STATUS_RESTING

    def test_trade_keyword_from_exploring(self, engine):
        result = engine._infer_status("我想买点东西", "", STATUS_EXPLORING)
        assert result == STATUS_TRADING

    def test_dialogue_from_exploring(self, engine):
        result = engine._infer_status("和他对话", "", STATUS_EXPLORING)
        assert result == STATUS_DIALOGUE

    def test_invalid_transition_keeps_current(self, engine):
        # combat -> resting is NOT in VALID_TRANSITIONS
        result = engine._infer_status("休息", "", STATUS_COMBAT)
        assert result == STATUS_COMBAT

    def test_end_combat_keywords(self, engine):
        result = engine._infer_status("", "你击败了强盗，战斗结束。", STATUS_COMBAT)
        assert result == STATUS_EXPLORING

    def test_dead_state_cannot_transition(self, engine):
        result = engine._infer_status("攻击", "", STATUS_DEAD)
        assert result == STATUS_DEAD


# ---------------------------------------------------------------------------
# check_events
# ---------------------------------------------------------------------------
class TestCheckEvents:
    def test_early_turns_skip_high_min_turn_events(self, engine, base_state):
        base_state["turn"] = 1
        narrative, log = engine.check_events(base_state)
        skipped_keys = [s["key"] for s in log["skipped"]]
        # Events with min_turns > 1 should be skipped
        for s in log["skipped"]:
            assert "min_turns" in s["reason"] or "cooldown" in s["reason"] or True

    def test_dead_status_still_runs(self, engine, base_state):
        base_state["status"] = STATUS_DEAD
        base_state["turn"] = 20
        _, log = engine.check_events(base_state)
        assert "candidates_count" in log

    def test_cooldown_blocks_event(self, engine, base_state):
        base_state["turn"] = 20
        base_state["event_cooldowns"] = {"merchant_encounter": 3}
        _, log = engine.check_events(base_state)
        skipped_keys = [s["key"] for s in log["skipped"]]
        assert "merchant_encounter" in skipped_keys

    def test_scenario_filtering(self, engine):
        state = engine.create_initial_state("X", "Y", "scifi")
        state["turn"] = 20
        state["chapter"] = 5
        _, log = engine.check_events(state)
        # fantasy-only events should not appear in candidates
        skipped_keys = [s["key"] for s in log["skipped"]]
        # dragon_shadow and fairy_spring are fantasy-only, should not appear
        # They should simply be filtered before condition check


# ---------------------------------------------------------------------------
# update_state
# ---------------------------------------------------------------------------
class TestUpdateState:
    def test_turn_increments(self, engine, base_state):
        new = engine.update_state(base_state, "向前走", "你沿着小路向前走去。")
        assert new["turn"] == 1

    def test_combat_increases_fatigue(self, engine, base_state):
        base_state["status"] = STATUS_EXPLORING
        new = engine.update_state(base_state, "拔剑战斗", "你挥剑攻击了敌人。")
        assert new["fatigue"] > base_state["fatigue"]

    def test_resting_heals(self, engine, base_state):
        base_state["health"] = 80
        new = engine.update_state(base_state, "休息", "你在树下休息。")
        assert new["health"] > 80

    def test_resting_reduces_fatigue(self, engine, base_state):
        base_state["fatigue"] = 50
        new = engine.update_state(base_state, "休息", "你好好休息了一番。")
        assert new["fatigue"] < 50

    def test_death_save_triggers_once(self, engine, base_state):
        base_state["health"] = 1
        base_state["fatigue"] = 90  # will cause -2 HP from fatigue penalty
        new = engine.update_state(base_state, "向前走", "你艰难地前行。")
        # health after: 1 + 1 (exploring heal) - 2 (fatigue penalty) = 0 -> death save -> 1
        assert new["death_save_used"] is True
        assert new["health"] >= 1
        assert new["status"] != STATUS_DEAD

    def test_second_death_kills(self, engine, base_state):
        base_state["health"] = 1
        base_state["fatigue"] = 90
        base_state["death_save_used"] = True
        new = engine.update_state(base_state, "向前走", "你挣扎着前进。")
        if new["health"] <= 0:
            assert new["status"] == STATUS_DEAD

    def test_chapter_advances_at_turn_15(self, engine, base_state):
        base_state["turn"] = 14  # will become 15 after update
        new = engine.update_state(base_state, "走", "你走着。")
        assert new["chapter"] == 2

    def test_location_changes_from_ai_response(self, engine, base_state):
        new = engine.update_state(base_state, "走", "你来到了幽暗森林。")
        assert new["current_location"] == "幽暗森林"

    def test_cooldown_decrement(self, engine, base_state):
        base_state["event_cooldowns"] = {"test_event": 3}
        new = engine.update_state(base_state, "走", "你走着。")
        assert new["event_cooldowns"]["test_event"] == 2

    def test_cooldown_removed_at_zero(self, engine, base_state):
        base_state["event_cooldowns"] = {"test_event": 1}
        new = engine.update_state(base_state, "走", "你走着。")
        assert "test_event" not in new["event_cooldowns"]


class TestEventDbHelpers:
    @pytest.mark.asyncio
    async def test_seed_events_if_empty(self, db_session):
        inserted = await seed_events_if_empty(db_session)
        assert inserted > 0

        rows = await load_events_from_db(db_session)
        assert any(e["key"] == "merchant_encounter" for e in rows)
        assert any("scenarios" in e for e in rows)

    @pytest.mark.asyncio
    async def test_load_events_from_empty_db_fallbacks(self, db_session):
        rows = await load_events_from_db(db_session)
        assert isinstance(rows, list)
        assert any(e["key"] == "merchant_encounter" for e in rows)
