"""Research Agent — Phase 5 full implementation.

Pipeline: web search → fetch top pages concurrently → synthesize with the
reasoning model → cited executive report → auto-save to knowledge base.
"""

import asyncio
import re
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.services import audit
from app.services.web_search import SearchResult, get_web_search_service

logger = get_logger(__name__)

MAX_SOURCES = 4

_SYNTHESIZE_PROMPT = """You are a research analyst writing an executive report.

Research question: {question}

Sources:
{sources}

Write a structured report:
1. *Executive Summary* — 2-3 sentences answering the question directly
2. *Key Findings* — bullet points, cite sources inline like [1], [2]
3. *Bottom Line* — one-sentence recommendation or takeaway

Rules:
- Use ONLY the provided sources; if they conflict, say so
- If the question asks to compare things, structure findings as a comparison
- Every factual claim needs a citation [n]
- WhatsApp formatting: *bold*, _italic_, plain bullets. No markdown headers.
- Keep it under 350 words."""

# deepseek-r1 emits <think>...</think> reasoning blocks — strip before delivery
_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)


class ResearchAgent:
    def __init__(self, ollama, web_search=None) -> None:
        self._ollama = ollama
        self._settings = get_settings()
        self._web_search = web_search or get_web_search_service()

    # ── Coordinator entry point ───────────────────────────────────────────────

    async def handle_command(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        intent: str,
        message: str,
    ) -> str:
        try:
            return await self.research(db, user_id, message)
        except RuntimeError as exc:
            return f"🔍 Research isn't fully set up: {exc!s}"
        except Exception as exc:
            logger.error("research_agent_error", error=str(exc))
            await audit.log_action(
                db, action="research.error", user_id=user_id,
                status="error", details={"error": str(exc)},
            )
            return f"⚠️ Research error: {exc!s}"

    # ── Pipeline ──────────────────────────────────────────────────────────────

    async def research(self, db: AsyncSession, user_id: uuid.UUID, question: str) -> str:
        results = await self._web_search.search(question, limit=MAX_SOURCES + 2)
        if not results:
            return "🔍 I couldn't find any web results for that. Try rephrasing?"

        sources = await self._fetch_sources(results[: MAX_SOURCES + 2])
        if not sources:
            return (
                "🔍 I found results but couldn't read any of the pages "
                "(sites may be blocking bots). Try a different question."
            )

        report = await self._synthesize(question, sources)
        citations = "\n".join(
            f"[{i + 1}] {s.title} — {s.url}" for i, (s, _) in enumerate(sources)
        )
        full_report = f"🔍 *Research Report*\n\n{report}\n\n📎 *Sources:*\n{citations}"

        await audit.log_action(
            db, action="research.report", user_id=user_id,
            details={"question": question[:200], "sources": len(sources)},
        )
        await self._save_to_knowledge_base(db, user_id, question, full_report)
        return full_report

    async def _fetch_sources(
        self, results: list[SearchResult]
    ) -> list[tuple[SearchResult, str]]:
        """Fetch pages concurrently; keep up to MAX_SOURCES readable ones."""
        texts = await asyncio.gather(
            *(self._web_search.fetch_page(r.url) for r in results)
        )
        sources = []
        for result, text in zip(results, texts):
            content = text or result.snippet
            if content.strip():
                sources.append((result, content))
            if len(sources) >= MAX_SOURCES:
                break
        return sources

    async def _synthesize(
        self, question: str, sources: list[tuple[SearchResult, str]]
    ) -> str:
        source_text = "\n\n".join(
            f"[{i + 1}] {s.title} ({s.url})\n{text}"
            for i, (s, text) in enumerate(sources)
        )
        result = await self._ollama.chat(
            messages=[
                {
                    "role": "user",
                    "content": _SYNTHESIZE_PROMPT.format(
                        question=question, sources=source_text
                    ),
                }
            ],
            model=self._settings.OLLAMA_REASONING_MODEL,
            temperature=0.3,
        )
        return _THINK_RE.sub("", result["content"]).strip()

    async def _save_to_knowledge_base(
        self, db: AsyncSession, user_id: uuid.UUID, question: str, report: str
    ) -> None:
        """Best-effort: index the report so future questions can cite it."""
        try:
            from app.agents.knowledge_agent import KnowledgeAgent

            agent = KnowledgeAgent(ollama=self._ollama)
            await agent._ingest(
                db, user_id,
                data=report.encode(),
                filename="report.md",
                title=f"Research: {question[:70]}",
                source_type="research",
            )
        except Exception as exc:
            logger.warning("research_kb_save_failed", error=str(exc))
