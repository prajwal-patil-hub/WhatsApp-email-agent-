"""Knowledge Agent — Phase 4. Stub with interface defined."""

from dataclasses import dataclass


@dataclass
class KnowledgeResult:
    answer: str
    source_title: str
    source_type: str
    relevance_score: float
    chunk_text: str


class KnowledgeAgent:
    """
    Phase 4 implementation will include:
    - PDF, DOCX, TXT, Markdown ingestion
    - Web page ingestion
    - Chunking (recursive character splitter)
    - Embedding generation via Ollama
    - Qdrant vector storage and semantic search
    - Answer grounded in retrieved chunks (RAG)
    - Notion integration
    """

    async def ingest_document(self, user_id: str, file_path: str, title: str | None = None) -> str:
        raise NotImplementedError("Knowledge Agent available in Phase 4")

    async def search(self, user_id: str, query: str, limit: int = 5) -> list[KnowledgeResult]:
        raise NotImplementedError("Knowledge Agent available in Phase 4")

    async def answer(self, user_id: str, question: str) -> str:
        raise NotImplementedError("Knowledge Agent available in Phase 4")
