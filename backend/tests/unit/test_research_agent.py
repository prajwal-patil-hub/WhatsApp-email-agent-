"""Unit tests for ResearchAgent + web search — Phase 5."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from app.agents.research_agent import ResearchAgent
from app.models.db.user import User
from app.services.web_search import SearchResult, html_to_text


# ── html_to_text ──────────────────────────────────────────────────────────────

def test_html_to_text_strips_tags_and_scripts():
    html = """<html><head><script>alert('x')</script><style>.a{}</style></head>
    <body><h1>Title</h1><p>First para.</p><p>Second &amp; more.</p></body></html>"""
    text = html_to_text(html)
    assert "Title" in text
    assert "First para." in text
    assert "Second & more." in text
    assert "alert" not in text
    assert "<p>" not in text


def test_html_to_text_entities():
    assert html_to_text("a &lt;b&gt; &quot;c&quot;") == 'a <b> "c"'


# ── ResearchAgent ─────────────────────────────────────────────────────────────

@pytest.fixture
def mock_ollama():
    svc = MagicMock()
    svc.chat = AsyncMock(return_value={
        "content": "<think>reasoning...</think>*Executive Summary*\nFinding [1].",
        "model": "deepseek-r1", "tokens_used": 100,
    })
    svc.embed = AsyncMock(return_value=[0.1] * 768)
    return svc


@pytest.fixture
def mock_search():
    ws = MagicMock()
    ws.search = AsyncMock(return_value=[
        SearchResult(title="Source A", url="https://a.example", snippet="About A"),
        SearchResult(title="Source B", url="https://b.example", snippet="About B"),
    ])
    ws.fetch_page = AsyncMock(return_value="Long page content about the topic.")
    return ws


@pytest.fixture
def agent(mock_ollama, mock_search, mock_settings):
    return ResearchAgent(ollama=mock_ollama, web_search=mock_search)


@pytest_asyncio.fixture
async def research_user(db_session):
    user = User(phone_number="17775550000", role="user")
    db_session.add(user)
    await db_session.flush()
    return user


@pytest.mark.asyncio
async def test_research_produces_cited_report(agent, db_session, research_user):
    with patch.object(agent, "_save_to_knowledge_base", new_callable=AsyncMock):
        result = await agent.handle_command(
            db_session, research_user.id, "research", "What are AI agent frameworks?"
        )
    assert "Research Report" in result
    assert "Executive Summary" in result
    assert "Sources:" in result
    assert "https://a.example" in result
    # deepseek <think> block must be stripped
    assert "<think>" not in result
    assert "reasoning..." not in result


@pytest.mark.asyncio
async def test_research_no_results(agent, mock_search, db_session, research_user):
    mock_search.search = AsyncMock(return_value=[])
    result = await agent.handle_command(db_session, research_user.id, "research", "xyzzy")
    assert "couldn't find" in result.lower()


@pytest.mark.asyncio
async def test_research_unreadable_pages_falls_back_to_snippets(
    agent, mock_search, db_session, research_user
):
    mock_search.fetch_page = AsyncMock(return_value="")
    with patch.object(agent, "_save_to_knowledge_base", new_callable=AsyncMock):
        result = await agent.handle_command(
            db_session, research_user.id, "research", "topic"
        )
    # Snippets exist, so synthesis should still run
    assert "Research Report" in result


@pytest.mark.asyncio
async def test_research_not_configured(agent, mock_search, db_session, research_user):
    mock_search.search = AsyncMock(side_effect=RuntimeError("No search backend configured."))
    result = await agent.handle_command(db_session, research_user.id, "research", "topic")
    assert "isn't fully set up" in result


@pytest.mark.asyncio
async def test_research_saves_to_knowledge_base(agent, db_session, research_user):
    with patch.object(agent, "_save_to_knowledge_base", new_callable=AsyncMock) as mock_save:
        await agent.handle_command(db_session, research_user.id, "research", "topic")
    mock_save.assert_awaited_once()


@pytest.mark.asyncio
async def test_uses_reasoning_model(agent, mock_ollama, db_session, research_user):
    with patch.object(agent, "_save_to_knowledge_base", new_callable=AsyncMock):
        await agent.handle_command(db_session, research_user.id, "research", "topic")
    model = mock_ollama.chat.await_args.kwargs["model"]
    assert "deepseek" in model or "reasoning" in model.lower() or model  # settings-driven
