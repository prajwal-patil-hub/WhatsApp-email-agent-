"""Research Agent — Phase 5. Stub with interface defined."""

from dataclasses import dataclass


@dataclass
class ResearchReport:
    title: str
    summary: str
    sections: list[dict[str, str]]
    citations: list[str]
    generated_at: str


class ResearchAgent:
    """
    Phase 5 implementation will include:
    - SearXNG / Brave Search API integration
    - Multi-source content fetching and synthesis
    - Executive summary generation
    - Citation tracking
    - Report export (Markdown + PDF)
    - Research archive in knowledge base
    """

    async def research(self, query: str, depth: str = "standard") -> ResearchReport:
        raise NotImplementedError("Research Agent available in Phase 5")

    async def compare(self, topics: list[str]) -> ResearchReport:
        raise NotImplementedError("Research Agent available in Phase 5")
