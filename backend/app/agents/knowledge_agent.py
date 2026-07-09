"""Knowledge Agent — Phase 4 full implementation.

RAG over the user's documents and notes: ingest → chunk → embed → Qdrant,
then answer questions grounded in retrieved chunks with source citations.
"""

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.db.knowledge import KnowledgeItem
from app.services import audit
from app.services.documents import chunk_text, content_hash, extract_text

logger = get_logger(__name__)


@dataclass
class KnowledgeResult:
    answer: str
    source_title: str
    source_type: str
    relevance_score: float
    chunk_text: str


_RAG_ANSWER_PROMPT = """Answer the question using ONLY the provided context chunks.
If the context doesn't contain the answer, say so honestly — do not invent facts.
Cite sources inline like [1], [2] matching the chunk numbers.
Keep the answer WhatsApp-friendly: concise, plain language.

Context chunks:
{context}

Question: {question}"""


class KnowledgeAgent:
    def __init__(self, ollama, qdrant=None) -> None:
        self._ollama = ollama
        self._settings = get_settings()
        if qdrant is None:
            from app.services.qdrant import get_qdrant_service

            qdrant = get_qdrant_service()
        self._qdrant = qdrant

    # ── Coordinator entry point ───────────────────────────────────────────────

    async def handle_command(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        intent: str,
        message: str,
    ) -> str:
        try:
            if intent == "knowledge_ingest":
                return await self.ingest_note(db, user_id, message)
            return await self.answer(db, user_id, message)
        except Exception as exc:
            logger.error("knowledge_agent_error", intent=intent, error=str(exc))
            await audit.log_action(
                db, action="knowledge.error", user_id=user_id,
                status="error", details={"error": str(exc)},
            )
            return f"⚠️ Knowledge base error: {exc!s}"

    # ── Ingestion ─────────────────────────────────────────────────────────────

    async def ingest_note(self, db: AsyncSession, user_id: uuid.UUID, text: str) -> str:
        """Ingest a WhatsApp text message as a knowledge note."""
        data = text.encode()
        return await self._ingest(
            db, user_id, data=data, filename="note.txt",
            title=text[:80], source_type="note",
        )

    async def ingest_document(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        data: bytes,
        filename: str,
        title: str | None = None,
    ) -> str:
        return await self._ingest(
            db, user_id, data=data, filename=filename,
            title=title or filename, source_type="document",
        )

    async def _ingest(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        data: bytes,
        filename: str,
        title: str,
        source_type: str,
    ) -> str:
        digest = content_hash(data)
        existing = (
            await db.execute(
                select(KnowledgeItem).where(KnowledgeItem.content_hash == digest)
            )
        ).scalar_one_or_none()
        if existing:
            return f"📚 Already in your knowledge base: *{existing.title or filename}*"

        text = extract_text(data, filename)
        chunks = chunk_text(text)
        if not chunks:
            return "🤔 That document appears to be empty — nothing to ingest."

        item = KnowledgeItem(
            user_id=user_id,
            title=title,
            source_type=source_type,
            content_hash=digest,
            status="processing",
        )
        db.add(item)
        await db.flush()

        embedded = 0
        for i, chunk in enumerate(chunks):
            try:
                vector = await self._ollama.embed(chunk)
                await self._qdrant.upsert(
                    collection=self._settings.QDRANT_KNOWLEDGE_COLLECTION,
                    vector=vector,
                    payload={
                        "user_id": str(user_id),
                        "knowledge_item_id": str(item.id),
                        "title": title,
                        "source_type": source_type,
                        "chunk_index": i,
                        "text": chunk,
                    },
                )
                embedded += 1
            except Exception as exc:
                logger.warning("chunk_embed_failed", chunk=i, error=str(exc))

        item.chunk_count = embedded
        item.status = "ready" if embedded else "failed"
        await db.flush()

        await audit.log_action(
            db, action="knowledge.ingest", user_id=user_id,
            resource_type="knowledge_item", resource_id=str(item.id),
            details={"title": title, "chunks": embedded, "source_type": source_type},
        )

        if not embedded:
            return "⚠️ Ingestion failed — couldn't generate embeddings. Is Ollama running with nomic-embed-text pulled?"
        return f"📚 *Ingested:* {title}\n{embedded} chunk{'s' if embedded != 1 else ''} indexed. Ask me anything about it!"

    # ── Search + RAG answer ───────────────────────────────────────────────────

    async def search(
        self, db: AsyncSession, user_id: uuid.UUID, query: str, limit: int = 5
    ) -> list[KnowledgeResult]:
        vector = await self._ollama.embed(query)
        hits = await self._qdrant.search(
            collection=self._settings.QDRANT_KNOWLEDGE_COLLECTION,
            vector=vector,
            user_id=str(user_id),
            limit=limit,
        )
        return [
            KnowledgeResult(
                answer="",
                source_title=h.get("title", "untitled"),
                source_type=h.get("source_type", "document"),
                relevance_score=h.get("score", 0.0),
                chunk_text=h.get("text", ""),
            )
            for h in hits
        ]

    async def answer(self, db: AsyncSession, user_id: uuid.UUID, question: str) -> str:
        results = await self.search(db, user_id, question, limit=5)
        await audit.log_action(
            db, action="knowledge.search", user_id=user_id,
            details={"question": question[:200], "hits": len(results)},
        )
        if not results:
            return (
                "🧠 I don't have anything in your knowledge base about that yet. "
                "Send me a document (PDF/DOCX/TXT) or say 'remember this: ...' to add knowledge."
            )

        context = "\n\n".join(
            f"[{i + 1}] (from: {r.source_title})\n{r.chunk_text}"
            for i, r in enumerate(results)
        )
        result = await self._ollama.chat(
            messages=[
                {
                    "role": "user",
                    "content": _RAG_ANSWER_PROMPT.format(context=context, question=question),
                }
            ],
            model=self._settings.OLLAMA_DEFAULT_MODEL,
            temperature=0.2,
        )
        answer = result["content"].strip()
        sources = sorted({r.source_title for r in results})
        return f"{answer}\n\n📎 _Sources: {', '.join(sources)}_"
