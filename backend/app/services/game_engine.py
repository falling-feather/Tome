import random
import logging
from typing import Optional

logger = logging.getLogger("inkless")

# ---------------------------------------------------------------------------
# 状态常量
# ---------------------------------------------------------------------------
STATUS_EXPLORING = "exploring"
STATUS_COMBAT = "combat"
STATUS_RESTING = "resting"
STATUS_TRADING = "trading"
STATUS_DIALOGUE = "dialogue"
STATUS_DEAD = "dead"

VALID_TRANSITIONS = {
    STATUS_EXPLORING: {STATUS_COMBAT, STATUS_RESTING, STATUS_TRADING, STATUS_DIALOGUE, STATUS_EXPLORING},
    STATUS_COMBAT: {STATUS_EXPLORING, STATUS_DEAD, STATUS_COMBAT},
    STATUS_RESTING: {STATUS_EXPLORING, STATUS_RESTING},
    STATUS_TRADING: {STATUS_EXPLORING, STATUS_TRADING, STATUS_DIALOGUE},
    STATUS_DIALOGUE: {STATUS_EXPLORING, STATUS_COMBAT, STATUS_TRADING, STATUS_DIALOGUE},
    STATUS_DEAD: set(),
}

# ---------------------------------------------------------------------------
# 事件池 — 按场景/通用分类, 带前置条件系统
# ---------------------------------------------------------------------------
EVENTS = [
    # ---- 通用事件 ----
    {
        "key": "merchant_encounter", "category": "character", "title": "旅行商人",
        "description": "一位神秘的旅行商人出现在你面前，他的货车上堆满了奇异的物品。",
        "conditions": {"min_turns": 3}, "weight": 1.2, "cooldown": 5,
        "effects": {"money": -10}, "scenarios": [],
    },
    {
        "key": "ambush", "category": "risk", "title": "路边伏击",
        "description": "几个盗贼从灌木丛中跳出，拦住了你的去路！",
        "conditions": {"min_turns": 5, "min_health": 30}, "weight": 0.8, "cooldown": 8,
        "effects": {"health": -15, "status": STATUS_COMBAT}, "scenarios": [],
    },
    {
        "key": "hidden_treasure", "category": "resource", "title": "隐藏宝藏",
        "description": "你在一块松动的石板下发现了一个古老的箱子。",
        "conditions": {"min_turns": 4}, "weight": 0.6, "cooldown": 10,
        "effects": {"money": 30}, "scenarios": [],
    },
    {
        "key": "mysterious_traveler", "category": "character", "title": "神秘旅人",
        "description": "一名身披斗篷的旅人在篝火旁向你招手，似乎有重要的事情要告诉你。",
        "conditions": {"min_turns": 2}, "weight": 1.0, "cooldown": 6,
        "effects": {"status": STATUS_DIALOGUE}, "scenarios": [],
    },
    {
        "key": "weather_storm", "category": "environment", "title": "突发暴风雨",
        "description": "天空突然乌云密布，狂风暴雨即将来临，你需要找到避雨的地方。",
        "conditions": {"min_turns": 6}, "weight": 0.7, "cooldown": 12,
        "effects": {"fatigue": 15}, "scenarios": [],
    },
    {
        "key": "ancient_ruins", "category": "environment", "title": "远古遗迹",
        "description": "你偶然发现了一处被藤蔓覆盖的远古遗迹入口，石壁上刻着神秘的符文。",
        "conditions": {"min_turns": 8, "require_status": STATUS_EXPLORING},
        "weight": 0.5, "cooldown": 15, "effects": {}, "scenarios": [],
    },
    {
        "key": "wounded_animal", "category": "character", "title": "受伤的野兽",
        "description": "路边躺着一只受伤的幼狼，它用哀求的眼神看着你。",
        "conditions": {"min_turns": 3}, "weight": 0.9, "cooldown": 7,
        "effects": {}, "scenarios": [],
    },
    {
        "key": "village_festival", "category": "plot", "title": "村庄节日",
        "description": "远处传来欢快的音乐声，附近的村庄似乎正在举办一场盛大的庆典。",
        "conditions": {"min_turns": 10}, "weight": 0.4, "cooldown": 20,
        "effects": {"fatigue": -20, "status": STATUS_RESTING}, "scenarios": [],
    },
    {
        "key": "dark_cave", "category": "environment", "title": "黑暗洞穴",
        "description": "崖壁上有一个幽深的洞穴，里面传来微弱的光芒和低沉的回响。",
        "conditions": {"min_turns": 5}, "weight": 0.7, "cooldown": 10,
        "effects": {}, "scenarios": [],
    },
    {
        "key": "herb_field", "category": "resource", "title": "药草田",
        "description": "你发现了一片野生药草田，这些草药看起来能恢复体力。",
        "conditions": {"min_turns": 4}, "weight": 0.8, "cooldown": 8,
        "effects": {"health": 20}, "scenarios": [],
    },
    {
        "key": "bounty_board", "category": "plot", "title": "悬赏公告",
        "description": "路边的告示牌上贴着一张悬赏公告，上面描述了附近出没的危险怪物。",
        "conditions": {"min_turns": 7}, "weight": 0.6, "cooldown": 12,
        "effects": {"quest_flag": "bounty_active"}, "scenarios": [],
    },
    {
        "key": "fallen_knight", "category": "character", "title": "倒下的骑士",
        "description": "一名身穿残破铠甲的骑士倒在路旁，他的剑深深插在地上。",
        "conditions": {"min_turns": 6}, "weight": 0.5, "cooldown": 15,
        "effects": {"status": STATUS_DIALOGUE}, "scenarios": [],
    },
    # ---- 奇幻专属 ----
    {
        "key": "dragon_shadow", "category": "risk", "title": "龙影掠过",
        "description": "一道巨大的阴影从天空掠过，伴随着震耳欲聋的咆哮——是龙！所有人都在恐惧中四散奔逃。",
        "conditions": {"min_turns": 12, "min_chapter": 2}, "weight": 0.3, "cooldown": 25,
        "effects": {"fatigue": 10}, "scenarios": ["fantasy"],
    },
    {
        "key": "fairy_spring", "category": "resource", "title": "精灵泉水",
        "description": "一汪散发着淡蓝色光芒的泉水，空气中弥漫着神秘的魔力气息。传说饮下泉水能恢复伤势。",
        "conditions": {"min_turns": 6, "max_health_pct": 70}, "weight": 0.7, "cooldown": 15,
        "effects": {"health": 30, "fatigue": -15}, "scenarios": ["fantasy"],
    },
    {
        "key": "magic_merchant", "category": "character", "title": "魔法物品商",
        "description": "一个漂浮在空中的小摊位挡住了去路。摊主是一只会说话的猫头鹰，它兜售各种附魔饰品。",
        "conditions": {"min_turns": 5, "min_money": 20}, "weight": 0.6, "cooldown": 12,
        "effects": {"status": STATUS_TRADING}, "scenarios": ["fantasy"],
    },
    # ---- 科幻专属 ----
    {
        "key": "alien_signal", "category": "plot", "title": "不明信号",
        "description": "飞船的通讯面板突然亮起，接收到一段来自未知来源的加密信号，坐标指向附近一颗无人记录的星球。",
        "conditions": {"min_turns": 4}, "weight": 0.8, "cooldown": 10,
        "effects": {"quest_flag": "alien_signal_received"}, "scenarios": ["scifi"],
    },
    {
        "key": "space_pirates", "category": "risk", "title": "星际海盗",
        "description": "警报！三艘海盗快艇正在逼近。它们切断了你的超空间引擎信号，要求你交出货物。",
        "conditions": {"min_turns": 8, "min_health": 40}, "weight": 0.5, "cooldown": 15,
        "effects": {"health": -20, "status": STATUS_COMBAT}, "scenarios": ["scifi"],
    },
    {
        "key": "derelict_station", "category": "environment", "title": "废弃空间站",
        "description": "雷达探测到一座早已被遗弃的空间站。站内似乎仍有微弱的能量反应。",
        "conditions": {"min_turns": 7}, "weight": 0.6, "cooldown": 12,
        "effects": {}, "scenarios": ["scifi"],
    },
    # ---- 武侠专属 ----
    {
        "key": "martial_challenge", "category": "risk", "title": "武林挑战",
        "description": "一名傲慢的刀客拦在路中央，扬言要与你一较高下，江湖人都在围观。",
        "conditions": {"min_turns": 5, "min_health": 50}, "weight": 0.7, "cooldown": 10,
        "effects": {"health": -10, "status": STATUS_COMBAT}, "scenarios": ["wuxia"],
    },
    {
        "key": "secret_manual", "category": "resource", "title": "残缺秘籍",
        "description": "在一处破败的藏书洞中，你发现了一本残缺的武功秘籍，上面画着精妙的内功运行路线。",
        "conditions": {"min_turns": 10, "min_chapter": 2}, "weight": 0.4, "cooldown": 20,
        "effects": {"quest_flag": "secret_manual_found"}, "scenarios": ["wuxia"],
    },
    {
        "key": "tea_master", "category": "character", "title": "茶楼高人",
        "description": "茶楼角落坐着一位白发老者，他悠然品茶，浑身散发出深不可测的气息。他似乎对你颇感兴趣。",
        "conditions": {"min_turns": 3}, "weight": 0.9, "cooldown": 8,
        "effects": {"fatigue": -10, "status": STATUS_DIALOGUE}, "scenarios": ["wuxia"],
    },
]

SCENARIOS = {
    "fantasy": {
        "name": "幽暗大陆",
        "intro": "欢迎来到幽暗大陆——一片被古老魔法和危险生物统治的神秘世界。",
        "locations": ["边境小镇", "幽暗森林", "矿山洞穴", "古老神殿", "荒废城堡", "精灵湖畔"],
    },
    "scifi": {
        "name": "星际纪元",
        "intro": "公元3077年，你是一名星际探索者，驾驶着「曙光号」飞船穿越未知星域。",
        "locations": ["空间站", "荒芜星球", "废弃飞船", "地下城市", "量子虫洞", "贸易港口"],
    },
    "wuxia": {
        "name": "江湖风云",
        "intro": "烽烟四起的武林中，你是一名初出茅庐的剑客，怀揣着不为人知的秘密踏上江湖路。",
        "locations": ["客栈", "竹林", "山巅古刹", "繁华市集", "密道", "剑庐"],
    },
}

# 动作关键词 → 状态映射
ACTION_STATUS_MAP = {
    STATUS_COMBAT: ["攻击", "战斗", "打", "杀", "砍", "射", "拔剑", "出招", "fight", "attack"],
    STATUS_RESTING: ["休息", "睡觉", "扎营", "歇息", "打坐", "冥想", "rest", "sleep"],
    STATUS_TRADING: ["买", "卖", "交易", "购买", "出售", "trade", "buy", "sell"],
    STATUS_DIALOGUE: ["对话", "交谈", "询问", "打听", "聊天", "talk", "ask"],
}


class GameEngine:

    # ------------------------------------------------------------------
    # 初始化
    # ------------------------------------------------------------------
    def create_initial_state(self, character_name: str, character_class: str, scenario: str) -> dict:
        sc = SCENARIOS.get(scenario, SCENARIOS["fantasy"])
        return {
            "character_name": character_name,
            "character_class": character_class,
            "scenario": scenario,
            "health": 100,
            "max_health": 100,
            "fatigue": 0,
            "money": 50,
            "current_location": sc["locations"][0],
            "turn": 0,
            "chapter": 1,
            "status": STATUS_EXPLORING,
            "events_triggered": [],
            "event_cooldowns": {},
            "quest_flags": {},
            "inventory": [],
            "affection_scores": {},
            "combat_streak": 0,
            "death_save_used": False,
        }

    def generate_intro(self, state: dict) -> str:
        scenario = state.get("scenario", "fantasy")
        sc = SCENARIOS.get(scenario, SCENARIOS["fantasy"])
        name = state.get("character_name", "旅行者")
        cls = state.get("character_class", "冒险者")
        loc = state.get("current_location", "未知之地")

        return (
            f"{sc['intro']}\n\n"
            f"你是{name}，一名{cls}。此刻你正身处【{loc}】。\n\n"
            f"周围的空气中弥漫着冒险的气息。街道上人来人往，偶尔传来铁匠铺的敲打声和酒馆里的喧闹。"
            f"你的旅程即将开始——你打算做什么？"
        )

    # ------------------------------------------------------------------
    # 动作校验
    # ------------------------------------------------------------------
    def validate_action(self, state: dict, user_action: str) -> tuple[bool, str]:
        """Return (is_valid, reason). Invalid actions get a descriptive reason."""
        status = state.get("status", STATUS_EXPLORING)

        if status == STATUS_DEAD:
            return False, "你的角色已经死亡，无法继续行动。请创建新的冒险。"

        # 疲劳过高时限制高强度行动
        fatigue = state.get("fatigue", 0)
        if fatigue >= 90:
            combat_kws = ACTION_STATUS_MAP[STATUS_COMBAT]
            if any(kw in user_action for kw in combat_kws):
                return False, "你已经筋疲力尽，无法进行战斗。先找个地方休息吧。"

        return True, ""

    # ------------------------------------------------------------------
    # 状态推断
    # ------------------------------------------------------------------
    def _infer_status(self, user_action: str, ai_response: str, current_status: str) -> str:
        """Infer the new status from action keywords and AI response."""
        combined = user_action + ai_response

        for target_status, keywords in ACTION_STATUS_MAP.items():
            if any(kw in user_action for kw in keywords):
                if target_status in VALID_TRANSITIONS.get(current_status, set()):
                    return target_status

        # 若 AI 描述中暗示战斗结束 → 回到探索
        end_combat_kws = ["战斗结束", "击败了", "离开了战场", "敌人倒下", "获胜"]
        if current_status == STATUS_COMBAT and any(kw in ai_response for kw in end_combat_kws):
            return STATUS_EXPLORING

        # 默认保持当前状态
        return current_status

    # ------------------------------------------------------------------
    # 事件检查 (完整条件系统 + 日志)
    # ------------------------------------------------------------------
    def check_events(self, state: dict) -> tuple[str, dict]:
        """Return (event_narrative, event_log). event_log includes candidates, selected, and skip reasons."""
        turn = state.get("turn", 0)
        cooldowns = state.get("event_cooldowns", {})
        scenario = state.get("scenario", "fantasy")
        status = state.get("status", STATUS_EXPLORING)
        health = state.get("health", 100)
        max_health = state.get("max_health", 100)
        money = state.get("money", 0)
        chapter = state.get("chapter", 1)

        hp_pct = (health / max_health * 100) if max_health > 0 else 100

        candidates = []
        skip_log = []

        for event in EVENTS:
            # 场景过滤
            evt_scenarios = event.get("scenarios", [])
            if evt_scenarios and scenario not in evt_scenarios:
                continue

            cond = event["conditions"]
            skip_reason = None

            if turn < cond.get("min_turns", 0):
                skip_reason = f"min_turns({cond['min_turns']})>current({turn})"
            elif cooldowns.get(event["key"], 0) > 0:
                skip_reason = f"cooldown remaining({cooldowns[event['key']]})"
            elif cond.get("require_status") and status != cond["require_status"]:
                skip_reason = f"require_status({cond['require_status']})!=current({status})"
            elif cond.get("min_health") and health < cond["min_health"]:
                skip_reason = f"min_health({cond['min_health']})>current({health})"
            elif cond.get("min_money") and money < cond["min_money"]:
                skip_reason = f"min_money({cond['min_money']})>current({money})"
            elif cond.get("min_chapter") and chapter < cond["min_chapter"]:
                skip_reason = f"min_chapter({cond['min_chapter']})>current({chapter})"
            elif cond.get("max_health_pct") and hp_pct > cond["max_health_pct"]:
                skip_reason = f"max_health_pct({cond['max_health_pct']})<current({hp_pct:.0f})"
            elif cond.get("require_flag") and cond["require_flag"] not in state.get("quest_flags", {}):
                skip_reason = f"missing flag({cond['require_flag']})"

            if skip_reason:
                skip_log.append({"key": event["key"], "reason": skip_reason})
            else:
                candidates.append(event)

        event_log = {
            "turn": turn,
            "candidates_count": len(candidates),
            "skipped": skip_log[:10],
            "selected": None,
            "roll_result": None,
        }

        if not candidates:
            return "", event_log

        # Weighted random selection
        weights = [e["weight"] for e in candidates]
        total = sum(weights)
        if total == 0:
            return "", event_log

        r = random.random() * total
        cumulative = 0
        selected = None
        for e, w in zip(candidates, weights):
            cumulative += w
            if r <= cumulative:
                selected = e
                break

        # 动态无事件概率：前10轮30%，之后降到15%
        no_event_chance = 0.30 if turn < 10 else 0.15
        roll = random.random()
        event_log["roll_result"] = {"no_event_threshold": no_event_chance, "roll": round(roll, 3)}

        if roll < no_event_chance:
            event_log["selected"] = {"key": selected["key"] if selected else None, "skipped_by_roll": True}
            return "", event_log

        if selected:
            event_log["selected"] = {"key": selected["key"], "title": selected["title"], "triggered": True}
            logger.info(f"Event triggered: {selected['key']} at turn {turn}")
            return f"{selected['title']}：{selected['description']}", event_log

        return "", event_log

    # ------------------------------------------------------------------
    # 结算器：统一状态更新
    # ------------------------------------------------------------------
    def update_state(self, state: dict, user_action: str, ai_response: str, event_log: dict | None = None) -> dict:
        state = dict(state)
        state["turn"] = state.get("turn", 0) + 1
        current_status = state.get("status", STATUS_EXPLORING)

        # 1. 冷却衰减
        cooldowns = dict(state.get("event_cooldowns", {}))
        for k in list(cooldowns.keys()):
            cooldowns[k] = max(0, cooldowns[k] - 1)
            if cooldowns[k] == 0:
                del cooldowns[k]
        state["event_cooldowns"] = cooldowns

        # 2. 应用事件效果
        if event_log and event_log.get("selected") and event_log["selected"].get("triggered"):
            evt_key = event_log["selected"]["key"]
            event_def = next((e for e in EVENTS if e["key"] == evt_key), None)
            if event_def:
                state["event_cooldowns"][evt_key] = event_def["cooldown"]
                triggered = list(state.get("events_triggered", []))
                triggered.append(evt_key)
                state["events_triggered"] = triggered[-50:]  # 保留最近50条

                effects = event_def.get("effects", {})
                for eff_key, eff_val in effects.items():
                    if eff_key == "health":
                        state["health"] = max(0, min(state.get("max_health", 100), state.get("health", 100) + eff_val))
                    elif eff_key == "fatigue":
                        state["fatigue"] = max(0, min(100, state.get("fatigue", 0) + eff_val))
                    elif eff_key == "money":
                        state["money"] = max(0, state.get("money", 0) + eff_val)
                    elif eff_key == "status":
                        if eff_val in VALID_TRANSITIONS.get(current_status, set()):
                            current_status = eff_val
                    elif eff_key == "quest_flag":
                        flags = dict(state.get("quest_flags", {}))
                        flags[eff_val] = True
                        state["quest_flags"] = flags

        # 3. 基于行动推断状态
        new_status = self._infer_status(user_action, ai_response, current_status)

        # 4. 数值结算
        if new_status == STATUS_COMBAT:
            state["combat_streak"] = state.get("combat_streak", 0) + 1
            state["fatigue"] = min(100, state.get("fatigue", 0) + 5)
            # 战斗中不自然恢复
        elif new_status == STATUS_RESTING:
            state["combat_streak"] = 0
            state["health"] = min(state.get("max_health", 100), state.get("health", 100) + 5)
            state["fatigue"] = max(0, state.get("fatigue", 0) - 10)
        else:
            state["combat_streak"] = 0
            state["fatigue"] = min(100, state.get("fatigue", 0) + 2)
            state["health"] = min(state.get("max_health", 100), state.get("health", 100) + 1)

        # 5. 疲劳惩罚
        if state["fatigue"] >= 80:
            state["health"] = max(0, state["health"] - 2)

        # 6. 死亡检测 + 死亡豁免
        if state["health"] <= 0:
            if not state.get("death_save_used"):
                state["health"] = 1
                state["death_save_used"] = True
                new_status = STATUS_EXPLORING  # 勉强逃脱
            else:
                new_status = STATUS_DEAD

        state["status"] = new_status

        # 7. 位置变化推断
        scenario = state.get("scenario", "fantasy")
        sc = SCENARIOS.get(scenario, SCENARIOS["fantasy"])
        for loc in sc["locations"]:
            if loc in ai_response:
                state["current_location"] = loc
                break

        # 8. 章节自动推进
        turn = state.get("turn", 0)
        if turn > 0 and turn % 15 == 0:
            state["chapter"] = state.get("chapter", 1) + 1

        return state
