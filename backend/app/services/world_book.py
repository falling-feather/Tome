"""
世界书服务 — 分层设定检索 + 种子数据
"""
import re
import logging
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from backend.app.models import WorldEntry

logger = logging.getLogger("inkless")

# ---------------------------------------------------------------------------
# 种子数据 — 每个场景的核心/章节/临时世界设定
# ---------------------------------------------------------------------------
SEED_ENTRIES: list[dict] = [
    # ====== 通用核心规则 ======
    {
        "scenario": "*", "layer": "core", "category": "rule", "title": "叙事基调",
        "keywords": "叙事,规则,基调,风格",
        "content": "本游戏以第二人称视角讲述冒险故事。叙事应生动、沉浸，避免说教和元叙事（如\"作为AI\"）。"
                   "保持200-400字的回复长度，每段末尾自然暗示2-3个行动方向。",
        "priority": 100,
    },
    {
        "scenario": "*", "layer": "core", "category": "rule", "title": "数值暗示规则",
        "keywords": "数值,暗示,生命值,金币,疲劳",
        "content": "永远不要在叙事中直接展示数字。用描写暗示变化："
                   "生命下降→'一阵剧痛传来'；金币增加→'钱袋沉甸甸'；疲劳升高→'双腿沉如灌铅'。"
                   "玩家可以通过右侧面板查看精确数值。",
        "priority": 90,
    },
    {
        "scenario": "*", "layer": "core", "category": "rule", "title": "角色行为边界",
        "keywords": "行为,边界,限制,禁止",
        "content": "角色不能凭空获得未描述的物品或能力。NPC不应突然改变立场除非有充分铺垫。"
                   "死亡应当有意义——不轻易杀死角色，但也不应回避危险的后果。",
        "priority": 85,
    },

    # ====== 奇幻 — 幽暗大陆 ======
    {
        "scenario": "fantasy", "layer": "core", "category": "lore", "title": "幽暗大陆概况",
        "keywords": "幽暗大陆,世界,历史,魔法",
        "content": "幽暗大陆是一片被远古魔法浸透的广袤土地。千年前的'魔潮浩劫'摧毁了旧文明，"
                   "留下遍布各地的遗迹和不稳定的魔力节点。五大种族——人类、精灵、矮人、兽人和龙裔——"
                   "在废墟上重建了松散的联盟，但暗流涌动。",
        "priority": 80,
    },
    {
        "scenario": "fantasy", "layer": "core", "category": "faction", "title": "白塔学院",
        "keywords": "白塔,学院,法师,魔法,组织",
        "content": "白塔学院是大陆最大的魔法研究机构，坐落于银月城中央。学院由大长老议会治理，"
                   "对外提供魔法咨询和稀有药剂，对内却进行着危险的禁忌实验。学院法师身着灰袍，"
                   "额头刺有星辰纹样。普通冒险者若想进入学院，至少需要3封推荐信。",
        "priority": 60,
    },
    {
        "scenario": "fantasy", "layer": "core", "category": "character", "title": "暮铁老人",
        "keywords": "暮铁,铁匠,NPC,锻造,武器",
        "content": "暮铁老人是边境小镇最受尊敬的铁匠。他沉默寡言，但技艺精湛——"
                   "传说他的真名是远古矮人王族后裔。他只在满月之夜打造特殊武器，"
                   "且从不问顾客的来历。他的眼睛是一只金色一只银色。",
        "priority": 50,
    },
    {
        "scenario": "fantasy", "layer": "core", "category": "location", "title": "边境小镇",
        "keywords": "边境小镇,小镇,酒馆,起点",
        "content": "边境小镇是连接人类王国与荒野的最后堡垒。镇上有'醉龙酒馆'（冒险者聚集地）、"
                   "暮铁铁匠铺、杂货铺'万物归一'、以及白塔学院的小型分部。"
                   "镇外北方是幽暗森林，东方是矿山洞穴，南方通往银月城。",
        "priority": 55,
    },
    {
        "scenario": "fantasy", "layer": "core", "category": "location", "title": "幽暗森林",
        "keywords": "幽暗森林,森林,精灵,危险",
        "content": "幽暗森林终年笼罩在浓雾中，树冠遮天蔽日。森林深处栖息着精灵族的隐秘聚落，"
                   "但外围充满了变异生物和魔力陷阱。林中有一座被遗忘的精灵神殿，"
                   "据说藏有魔潮浩劫前的知识。夜间尤其危险——会出现幽灵鹿群。",
        "priority": 55,
    },
    {
        "scenario": "fantasy", "layer": "core", "category": "item", "title": "星辰碎片",
        "keywords": "星辰碎片,魔法,稀有,道具",
        "content": "星辰碎片是魔潮浩劫后散落大陆的魔力结晶，外形如淡蓝色的玻璃碎片。"
                   "它们是魔法锻造和高级药剂的核心原料，也是白塔学院重金悬赏的收藏品。"
                   "碎片在月光下会发出微弱的脉动，有经验的冒险者以此来寻找它们。",
        "priority": 45,
    },
    {
        "scenario": "fantasy", "layer": "chapter", "category": "lore", "title": "第一章：启程",
        "keywords": "启程,开始,新手,教程",
        "content": "角色初到边境小镇，应先熟悉环境：与NPC交谈获取信息，购买基础装备，"
                   "了解周边地形。不宜立即进入高危区域。酒馆的告示板会提供适合新手的任务。",
        "chapter_min": 1, "chapter_max": 2, "priority": 70,
    },
    {
        "scenario": "fantasy", "layer": "chapter", "category": "lore", "title": "第二章：暗流",
        "keywords": "暗流,阴谋,调查,线索",
        "content": "进入第二章后，镇上开始出现异常事件——牲畜失踪、夜间有奇怪的吟唱声。"
                   "有传言说白塔学院的人在矿山深处进行秘密实验。冒险者需要收集线索，"
                   "选择是否介入。",
        "chapter_min": 2, "chapter_max": 3, "priority": 70,
    },

    # ====== 科幻 — 星际纪元 ======
    {
        "scenario": "scifi", "layer": "core", "category": "lore", "title": "星际纪元概况",
        "keywords": "星际,纪元,宇宙,文明,科技",
        "content": "公元3077年，人类已经通过量子跳跃引擎殖民了银河系的三个旋臂。"
                   "然而'大静默事件'让外围殖民地与核心世界失去了联系。玩家驾驶的'曙光号'"
                   "是最后一批探索失联区域的自由船只。星际联邦已名存实亡，各星区自治。",
        "priority": 80,
    },
    {
        "scenario": "scifi", "layer": "core", "category": "faction", "title": "星际联邦残余",
        "keywords": "联邦,军队,组织,法律",
        "content": "星际联邦的残余力量仍控制着几个核心星区。他们的巡逻舰偶尔出现在航线上，"
                   "要求查验货物和身份。联邦对自由船只态度复杂——既需要他们的情报，"
                   "又担心走私和叛乱。联邦军番号以'USF'开头。",
        "priority": 60,
    },
    {
        "scenario": "scifi", "layer": "core", "category": "character", "title": "艾拉AI",
        "keywords": "艾拉,AI,飞船,助手,曙光号",
        "content": "艾拉是曙光号的舰载AI。她性格温和但略带讽刺，对船长（玩家）忠诚但会质疑危险决策。"
                   "她的核心数据库在一次事故中部分损坏，偶尔会闪回出不属于自己的记忆片段——"
                   "这暗示她的AI核心来源并不简单。",
        "priority": 50,
    },
    {
        "scenario": "scifi", "layer": "core", "category": "location", "title": "空间站",
        "keywords": "空间站,补给,贸易,起点",
        "content": "阿尔法-7空间站是附近星区最大的中立贸易站。由一位叫'掮客麦克'的退役军人管理。"
                   "站上有维修坞、黑市、信息贩子和佣兵酒吧。进站需要支付100信用点停靠费。"
                   "站上禁止使用武器——违者会被气闸弹射出去。",
        "priority": 55,
    },
    {
        "scenario": "scifi", "layer": "core", "category": "item", "title": "量子跳跃核心",
        "keywords": "量子,跳跃,核心,引擎,FTL",
        "content": "量子跳跃核心是超光速旅行的关键组件。每次跳跃消耗等离子燃料，"
                   "核心需要冷却12小时才能再次使用。损坏的核心会导致'跳跃碎裂'——"
                   "飞船可能出现在目标偏移数光年的位置。核心是黑市上最抢手的货物之一。",
        "priority": 45,
    },
    {
        "scenario": "scifi", "layer": "chapter", "category": "lore", "title": "第一章：失联",
        "keywords": "失联,信号,任务,起始",
        "content": "飞船接收到来自失联殖民地'新伊甸'的微弱求救信号。信号断断续续，"
                   "但坐标清晰。船长需要决定是否前往调查——这意味着进入联邦标记为危险的区域。"
                   "空间站上的信息贩子可能知道更多关于新伊甸的情况。",
        "chapter_min": 1, "chapter_max": 2, "priority": 70,
    },

    # ====== 武侠 — 江湖风云 ======
    {
        "scenario": "wuxia", "layer": "core", "category": "lore", "title": "江湖风云概况",
        "keywords": "江湖,武林,门派,恩怨",
        "content": "当今武林，五大门派——少林、武当、峨嵋、昆仑、华山——表面维持着'武林盟约'，"
                   "实则各怀心思。最近十年，一个自称'暗流阁'的神秘组织悄然崛起，"
                   "接连暗杀了数位武林名宿，搅得江湖不宁。",
        "priority": 80,
    },
    {
        "scenario": "wuxia", "layer": "core", "category": "faction", "title": "暗流阁",
        "keywords": "暗流阁,刺客,组织,阴谋",
        "content": "暗流阁行事诡秘，成员皆戴银色面具。据传阁主身手深不可测，"
                   "连五大掌门联手也未能将其拿下。暗流阁的目标似乎不只是金钱——"
                   "他们在有计划地收集一种叫'天机残卷'的古老武学典籍。",
        "priority": 60,
    },
    {
        "scenario": "wuxia", "layer": "core", "category": "character", "title": "柳无涯",
        "keywords": "柳无涯,NPC,侠客,朋友,江湖",
        "content": "柳无涯是一名洒脱不羁的游侠，自称'天下第二剑客'。他嗜酒好赌，"
                   "但为人仗义，轻财重诺。他的剑法飘逸灵动，以'落花十三式'闻名。"
                   "他与暗流阁有深仇——其师父正是被暗流阁暗杀的名宿之一。",
        "priority": 50,
    },
    {
        "scenario": "wuxia", "layer": "core", "category": "location", "title": "客栈",
        "keywords": "客栈,酒楼,起点,驿站",
        "content": "'听风客栈'是江湖人口中的老牌歇脚处，坐落于通往各大门派的交汇路口。"
                   "掌柜老赵是个消息灵通的精明人物——关于最近的江湖动态，他总能说出个一二三。"
                   "客栈二楼是客房，后院有马厩。每逢初一十五会有江湖中人聚饮比武。",
        "priority": 55,
    },
    {
        "scenario": "wuxia", "layer": "core", "category": "location", "title": "竹林",
        "keywords": "竹林,清幽,修炼,练功",
        "content": "镇外半里有一片翠竹林，尤為清幽。传说一位隐居的剑仙曾在此练剑百年，"
                   "竹叶间偶尔能感受到残留的剑气。这里是练功冥想的好去处，"
                   "但深夜偶有野兽出没。竹林深处有一间破败的草庐。",
        "priority": 55,
    },
    {
        "scenario": "wuxia", "layer": "core", "category": "item", "title": "天机残卷",
        "keywords": "天机残卷,秘籍,武学,宝物",
        "content": "天机残卷相传是上古武学宗师'天机子'毕生所学的总结，全卷共分七册。"
                   "每册记载着一种极致武学的修炼法门。暗流阁已收集到三册，"
                   "剩余四册散落在各大门派和隐秘之处。集齐七册据说可悟出天下无敌的武学。",
        "priority": 45,
    },
    {
        "scenario": "wuxia", "layer": "chapter", "category": "lore", "title": "第一章：初入江湖",
        "keywords": "初入江湖,新手,开始,起步",
        "content": "角色初出茅庐，在听风客栈落脚。应先与掌柜交谈了解近况，"
                   "在竹林练功提升实力。不宜直接挑战强敌。可以接一些简单的跑腿任务积攒声望。"
                   "客栈告示板有最新的江湖消息和悬赏。",
        "chapter_min": 1, "chapter_max": 2, "priority": 70,
    },
    {
        "scenario": "wuxia", "layer": "chapter", "category": "lore", "title": "第二章：暗流涌动",
        "keywords": "暗流,阴谋,线索,调查",
        "content": "进入第二章后，客栈附近开始出现暗流阁的探子。有人在暗中监视角色。"
                   "柳无涯可能在此时出现，与角色结识。一场武林聚会即将举行，"
                   "各方势力蠢蠢欲动。",
        "chapter_min": 2, "chapter_max": 3, "priority": 70,
    },
]


class WorldBookService:
    """世界书检索服务 — 基于关键词匹配的轻量级 RAG"""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ------------------------------------------------------------------
    # 种子数据初始化
    # ------------------------------------------------------------------
    async def seed_if_empty(self):
        """如果世界书为空，插入预设条目"""
        result = await self.db.execute(select(WorldEntry.id).limit(1))
        if result.scalar_one_or_none() is not None:
            return  # 已有数据

        for entry in SEED_ENTRIES:
            we = WorldEntry(
                scenario=entry["scenario"],
                layer=entry["layer"],
                category=entry["category"],
                title=entry["title"],
                keywords=entry["keywords"],
                content=entry["content"],
                chapter_min=entry.get("chapter_min", 0),
                chapter_max=entry.get("chapter_max", 0),
                priority=entry.get("priority", 0),
                is_active=True,
            )
            self.db.add(we)
        await self.db.commit()
        logger.info(f"世界书种子数据已写入: {len(SEED_ENTRIES)} 条")

    # ------------------------------------------------------------------
    # 检索
    # ------------------------------------------------------------------
    async def retrieve(
        self,
        scenario: str,
        chapter: int,
        context_text: str,
        layer: str | None = None,
        top_k: int = 6,
    ) -> list[dict]:
        """
        根据场景、章节和上下文文本检索最相关的世界书条目。

        使用关键词匹配 + 优先级排序:
        1. 筛选: scenario 匹配 (或通配 *)，章节范围，is_active
        2. 评分: keywords 与 context_text 的重叠度 + priority 权重
        3. 返回 top_k 条
        """
        # 构建查询条件
        conditions = [
            WorldEntry.is_active == True,
            WorldEntry.scenario.in_([scenario, "*"]),
        ]
        if layer:
            conditions.append(WorldEntry.layer == layer)

        result = await self.db.execute(
            select(WorldEntry).where(and_(*conditions))
        )
        entries = result.scalars().all()

        # 评分
        scored = []
        context_tokens = set(self._tokenize(context_text))

        for entry in entries:
            # 章节范围过滤
            if entry.chapter_min > 0 and chapter < entry.chapter_min:
                continue
            if entry.chapter_max > 0 and chapter > entry.chapter_max:
                continue

            # 关键词匹配评分
            entry_keywords = set(self._tokenize(entry.keywords + " " + entry.title))
            overlap = len(context_tokens & entry_keywords)
            score = overlap * 10 + entry.priority

            # core 层加权
            if entry.layer == "core":
                score += 20
            elif entry.layer == "chapter":
                score += 10

            scored.append({
                "id": entry.id,
                "title": entry.title,
                "layer": entry.layer,
                "category": entry.category,
                "content": entry.content,
                "score": score,
            })

        # 按分数降序排列，取 top_k
        scored.sort(key=lambda x: x["score"], reverse=True)
        selected = scored[:top_k]

        logger.debug(f"世界书检索: scenario={scenario}, chapter={chapter}, "
                     f"candidates={len(scored)}, selected={len(selected)}")
        return selected

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------
    @staticmethod
    def _tokenize(text: str) -> list[str]:
        """简易中文分词 — 按标点和空格分割 + 2-gram"""
        # 先分割
        tokens = re.split(r'[,，、\s;；。！？\n]+', text)
        tokens = [t.strip() for t in tokens if len(t.strip()) >= 1]

        # 对较长的 token 做 bigram
        bigrams = []
        for t in tokens:
            if len(t) >= 4:
                for i in range(len(t) - 1):
                    bigrams.append(t[i:i+2])

        return tokens + bigrams
