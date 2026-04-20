"""
EmbeddingService — 文本嵌入向量生成 (P1-13)

调用 OpenAI 兼容 /v1/embeddings 端点；密钥与 base_url 从管理员保存的 user_api_keys 读取
（默认 provider=settings.EMBEDDING_PROVIDER，通常为 openai）。
"""
from __future__ import annotations

import json
import logging
import math
import time
from typing import Iterable, Optional

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.config import settings
from backend.app.models import UserApiKey
from backend.app.services.llm_service import _get_shared_client

logger = logging.getLogger("inkless")


class EmbeddingService:
    """轻量嵌入服务：单例式，按调用查 admin 用户的 api key。"""

    def __init__(self, db: AsyncSession, admin_user_id: int = 1):
        self.db = db
        self.admin_user_id = admin_user_id
        self._cache: dict[str, tuple[float, list[float]]] = {}
        self._cache_ttl = 300  # 5 分钟缓存

    async def _get_credentials(self) -> Optional[tuple[str, str, str]]:
        provider = settings.EMBEDDING_PROVIDER
        result = await self.db.execute(
            select(UserApiKey).where(
                UserApiKey.user_id == self.admin_user_id,
                UserApiKey.provider == provider,
            )
        )
        row = result.scalar_one_or_none()
        if not row or not row.api_key:
            return None
        base_url = (row.base_url or "https://api.openai.com/v1").rstrip("/")
        model = settings.EMBEDDING_MODEL
        return row.api_key, base_url, model

    async def embed_text(self, text: str) -> Optional[list[float]]:
        """生成单条嵌入向量，失败/未配置返回 None。"""
        if not settings.EMBEDDING_ENABLED:
            return None
        if not text or not text.strip():
            return None

        # 缓存命中
        now = time.time()
        cached = self._cache.get(text)
        if cached and now - cached[0] < self._cache_ttl:
            return cached[1]

        creds = await self._get_credentials()
        if not creds:
            return None
        api_key, base_url, model = creds
        url = f"{base_url}/embeddings"
        try:
            resp = await _get_shared_client().post(
                url,
                json={"input": text, "model": model},
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=30.0,
            )
            resp.raise_for_status()
            data = resp.json()
            vec = data["data"][0]["embedding"]
            self._cache[text] = (now, vec)
            return vec
        except (httpx.HTTPError, KeyError, IndexError) as e:
            logger.warning(f"嵌入生成失败: {e}")
            return None

    async def embed_many(self, texts: Iterable[str]) -> list[Optional[list[float]]]:
        out: list[Optional[list[float]]] = []
        for t in texts:
            v = await self.embed_text(t)
            out.append(v)
        return out


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = 0.0
    na = 0.0
    nb = 0.0
    for x, y in zip(a, b):
        dot += x * y
        na += x * x
        nb += y * y
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (math.sqrt(na) * math.sqrt(nb))


def encode_embedding(vec: Optional[list[float]]) -> Optional[str]:
    if vec is None:
        return None
    return json.dumps(vec)


def decode_embedding(raw: Optional[str]) -> Optional[list[float]]:
    if not raw:
        return None
    try:
        v = json.loads(raw)
        if isinstance(v, list) and all(isinstance(x, (int, float)) for x in v):
            return [float(x) for x in v]
    except (json.JSONDecodeError, TypeError):
        return None
    return None
