"""WorldBookService 嵌入向量召回 (P1-13) 单测"""
import pytest
import pytest_asyncio

from backend.app.models import WorldEntry
from backend.app.services.world_book import WorldBookService
from backend.app.services.embeddings import (
    cosine_similarity,
    encode_embedding,
    decode_embedding,
)


class StubEmbedder:
    """固定映射的伪嵌入器，避免外部 API 调用。"""

    def __init__(self, mapping: dict[str, list[float]]):
        self.mapping = mapping
        self.calls: list[str] = []

    async def embed_text(self, text: str):
        self.calls.append(text)
        for key, vec in self.mapping.items():
            if key in text:
                return vec
        return [0.0, 0.0, 1.0]


# ---------------------------------------------------------------------------
# cosine + 编解码
# ---------------------------------------------------------------------------
def test_cosine_similarity_basic():
    assert cosine_similarity([1, 0, 0], [1, 0, 0]) == pytest.approx(1.0)
    assert cosine_similarity([1, 0, 0], [0, 1, 0]) == pytest.approx(0.0)
    assert cosine_similarity([1, 0, 0], [-1, 0, 0]) == pytest.approx(-1.0)
    assert cosine_similarity([], [1, 2]) == 0.0
    assert cosine_similarity([0, 0], [0, 0]) == 0.0


def test_embedding_codec_roundtrip():
    raw = [0.1, -0.2, 0.3]
    enc = encode_embedding(raw)
    assert isinstance(enc, str)
    assert decode_embedding(enc) == pytest.approx(raw)
    assert encode_embedding(None) is None
    assert decode_embedding(None) is None
    assert decode_embedding("not json") is None


# ---------------------------------------------------------------------------
# WorldBookService 混合检索
# ---------------------------------------------------------------------------
@pytest_asyncio.fixture
async def seeded_db(db_session):
    """插入两条 fantasy 条目用于测试。"""
    e1 = WorldEntry(
        scenario="fantasy", layer="core", category="lore",
        title="幽暗森林", keywords="森林,精灵",
        content="一片古老的森林", chapter_min=0, chapter_max=0,
        priority=0, is_active=True,
        embedding=encode_embedding([1.0, 0.0, 0.0]),
    )
    e2 = WorldEntry(
        scenario="fantasy", layer="core", category="lore",
        title="星辰碎片", keywords="魔法,稀有",
        content="远古魔法残留物", chapter_min=0, chapter_max=0,
        priority=0, is_active=True,
        embedding=encode_embedding([0.0, 1.0, 0.0]),
    )
    db_session.add_all([e1, e2])
    await db_session.commit()
    return db_session


@pytest.mark.asyncio
async def test_retrieve_uses_embedding_when_available(seeded_db):
    embedder = StubEmbedder({"森林": [1.0, 0.0, 0.0], "魔法": [0.0, 1.0, 0.0]})
    svc = WorldBookService(seeded_db, embedder=embedder)
    res = await svc.retrieve(
        scenario="fantasy", chapter=1,
        context_text="主角走入了陌生的森林",
        top_k=2,
    )
    # 第一条应是“幽暗森林”
    assert res[0]["title"] == "幽暗森林"
    assert res[0]["score"] > res[1]["score"]
    # embedder 至少被调用一次
    assert len(embedder.calls) == 1


@pytest.mark.asyncio
async def test_retrieve_falls_back_to_keyword_when_no_embedder(seeded_db):
    class NullEmbedder:
        async def embed_text(self, text):
            return None

    svc = WorldBookService(seeded_db, embedder=NullEmbedder())
    res = await svc.retrieve(
        scenario="fantasy", chapter=1,
        context_text="森林的精灵告诉你一段古老的传说",
        top_k=2,
    )
    # 没有向量时仍能基于 keyword 命中“幽暗森林”
    assert any(r["title"] == "幽暗森林" for r in res)


@pytest.mark.asyncio
async def test_reembed_all_skips_already_embedded(seeded_db):
    embedder = StubEmbedder({"幽暗": [1.0, 0.0, 0.0]})
    svc = WorldBookService(seeded_db, embedder=embedder)
    out = await svc.reembed_all(embedder=embedder)
    # 全部已有 embedding，应当全部 skipped
    assert out["skipped"] == 2
    assert out["processed"] == 0


@pytest.mark.asyncio
async def test_embed_entry_writes_vector(seeded_db):
    new_entry = WorldEntry(
        scenario="fantasy", layer="core", category="lore",
        title="新条目", keywords="未知", content="某些内容",
        chapter_min=0, chapter_max=0, priority=0, is_active=True,
        embedding=None,
    )
    seeded_db.add(new_entry)
    await seeded_db.commit()
    embedder = StubEmbedder({"新条目": [0.5, 0.5, 0.0]})
    svc = WorldBookService(seeded_db, embedder=embedder)
    ok = await svc.embed_entry(new_entry, embedder=embedder)
    assert ok is True
    assert new_entry.embedding is not None
    assert decode_embedding(new_entry.embedding) == pytest.approx([0.5, 0.5, 0.0])
