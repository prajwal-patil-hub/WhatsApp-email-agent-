"""Web search + page fetching — Phase 5.

Search: Brave Search API when BRAVE_SEARCH_API_KEY is set, else SearXNG
instance at SEARXNG_URL. Page fetch: httpx + regex HTML-to-text (no heavy
parser dependency; good enough for LLM synthesis).
"""

import re
from dataclasses import dataclass

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_SCRIPT_STYLE_RE = re.compile(r"<(script|style|noscript)[^>]*>.*?</\1>", re.DOTALL | re.IGNORECASE)
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"[ \t]{2,}")
_NL_RE = re.compile(r"\n{3,}")

MAX_PAGE_CHARS = 6000


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str


def html_to_text(html: str) -> str:
    text = _SCRIPT_STYLE_RE.sub(" ", html)
    text = re.sub(r"<(br|/p|/div|/h[1-6]|/li|/tr)[^>]*>", "\n", text, flags=re.IGNORECASE)
    text = _TAG_RE.sub(" ", text)
    text = (
        text.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<")
        .replace("&gt;", ">").replace("&quot;", '"').replace("&#39;", "'")
    )
    text = _WS_RE.sub(" ", text)
    text = "\n".join(line.strip() for line in text.splitlines())
    return _NL_RE.sub("\n\n", text).strip()


class WebSearchService:
    def __init__(self) -> None:
        self._settings = get_settings()

    async def search(self, query: str, limit: int = 5) -> list[SearchResult]:
        if self._settings.BRAVE_SEARCH_API_KEY:
            return await self._search_brave(query, limit)
        if self._settings.SEARXNG_URL:
            return await self._search_searxng(query, limit)
        raise RuntimeError(
            "No search backend configured. Set BRAVE_SEARCH_API_KEY or SEARXNG_URL."
        )

    async def _search_brave(self, query: str, limit: int) -> list[SearchResult]:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                "https://api.search.brave.com/res/v1/web/search",
                headers={
                    "X-Subscription-Token": self._settings.BRAVE_SEARCH_API_KEY,
                    "Accept": "application/json",
                },
                params={"q": query, "count": limit},
            )
            resp.raise_for_status()
            data = resp.json()
        return [
            SearchResult(
                title=r.get("title", ""),
                url=r.get("url", ""),
                snippet=r.get("description", ""),
            )
            for r in data.get("web", {}).get("results", [])[:limit]
        ]

    async def _search_searxng(self, query: str, limit: int) -> list[SearchResult]:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{self._settings.SEARXNG_URL.rstrip('/')}/search",
                params={"q": query, "format": "json"},
            )
            resp.raise_for_status()
            data = resp.json()
        return [
            SearchResult(
                title=r.get("title", ""),
                url=r.get("url", ""),
                snippet=r.get("content", ""),
            )
            for r in data.get("results", [])[:limit]
        ]

    async def fetch_page(self, url: str) -> str:
        """Fetch a page and return readable text, truncated for LLM context."""
        try:
            async with httpx.AsyncClient(
                timeout=20, follow_redirects=True,
                headers={"User-Agent": "Mozilla/5.0 (AI-Chief-of-Staff research bot)"},
            ) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                content_type = resp.headers.get("content-type", "")
                if "html" not in content_type and "text" not in content_type:
                    return ""
                return html_to_text(resp.text)[:MAX_PAGE_CHARS]
        except Exception as exc:
            logger.warning("page_fetch_failed", url=url, error=str(exc))
            return ""


_web_search_service: WebSearchService | None = None


def get_web_search_service() -> WebSearchService:
    global _web_search_service
    if _web_search_service is None:
        _web_search_service = WebSearchService()
    return _web_search_service
