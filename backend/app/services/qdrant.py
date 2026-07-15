"""Qdrant vector store service — Phase 4.

Wraps AsyncQdrantClient with collection bootstrap and typed helpers.
nomic-embed-text produces 768-dim vectors.
"""

import uuid
from typing import Any

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

VECTOR_SIZE = 768  # nomic-embed-text


class QdrantService:
    def __init__(self) -> None:
        from qdrant_client import AsyncQdrantClient

        settings = get_settings()
        self._settings = settings
        self._client = AsyncQdrantClient(
            url=settings.QDRANT_URL, api_key=settings.QDRANT_API_KEY
        )

    async def ensure_collections(self) -> None:
        from qdrant_client.models import Distance, VectorParams

        for name in (
            self._settings.QDRANT_MEMORY_COLLECTION,
            self._settings.QDRANT_KNOWLEDGE_COLLECTION,
        ):
            if not await self._client.collection_exists(name):
                await self._client.create_collection(
                    collection_name=name,
                    vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
                )
                logger.info("qdrant_collection_created", collection=name)

    async def upsert(
        self,
        collection: str,
        vector: list[float],
        payload: dict[str, Any],
        point_id: str | None = None,
    ) -> str:
        from qdrant_client.models import PointStruct

        point_id = point_id or str(uuid.uuid4())
        await self._client.upsert(
            collection_name=collection,
            points=[PointStruct(id=point_id, vector=vector, payload=payload)],
        )
        return point_id

    async def search(
        self,
        collection: str,
        vector: list[float],
        user_id: str,
        limit: int = 5,
        score_threshold: float = 0.3,
    ) -> list[dict[str, Any]]:
        """Search restricted to one user's points. Returns payload + score dicts."""
        from qdrant_client.models import FieldCondition, Filter, MatchValue

        results = await self._client.search(
            collection_name=collection,
            query_vector=vector,
            query_filter=Filter(
                must=[FieldCondition(key="user_id", match=MatchValue(value=user_id))]
            ),
            limit=limit,
            score_threshold=score_threshold,
        )
        return [{"score": r.score, **(r.payload or {})} for r in results]

    async def delete_points(self, collection: str, point_ids: list[str]) -> None:
        await self._client.delete(collection_name=collection, points_selector=point_ids)

    async def delete_by_filter(self, collection: str, key: str, value: str) -> None:
        from qdrant_client.models import FieldCondition, Filter, FilterSelector, MatchValue

        await self._client.delete(
            collection_name=collection,
            points_selector=FilterSelector(
                filter=Filter(must=[FieldCondition(key=key, match=MatchValue(value=value))])
            ),
        )

    async def is_available(self) -> bool:
        try:
            await self._client.get_collections()
            return True
        except Exception:
            return False


_qdrant_service: QdrantService | None = None


def get_qdrant_service() -> QdrantService:
    global _qdrant_service
    if _qdrant_service is None:
        _qdrant_service = QdrantService()
    return _qdrant_service
