"""Unit tests for KnowledgeAgent + document processing — Phase 4."""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.agents.knowledge_agent import KnowledgeAgent
from app.models.db.knowledge import KnowledgeItem
from app.models.db.user import User
from app.services.documents import chunk_text, content_hash, extract_text


# ── documents.py ──────────────────────────────────────────────────────────────

def test_extract_text_plain():
    assert extract_text(b"hello world", "notes.txt") == "hello world"
    assert extract_text(b"# Title\n\nBody", "readme.md") == "# Title\n\nBody"


def test_extract_text_unsupported():
    with pytest.raises(ValueError, match="Unsupported"):
        extract_text(b"binary", "image.png")


def test_chunk_short_text_single_chunk():
    assert chunk_text("short note") == ["short note"]


def test_chunk_empty():
    assert chunk_text("   ") == []


def test_chunk_long_text_respects_size_and_overlap():
    paras = "\n\n".join(f"Paragraph {i}. " + "x" * 300 for i in range(12))
    chunks = chunk_text(paras, chunk_size=1000, overlap=100)
    assert len(chunks) > 1
    assert all(len(c) <= 1000 for c in chunks)
    # Full coverage: every paragraph marker appears somewhere
    joined = " ".join(chunks)
    for i in range(12):
        assert f"Paragraph {i}." in joined


def test_chunk_giant_paragraph_hard_split():
    text = "y" * 5000
    chunks = chunk_text(text, chunk_size=1000, overlap=100)
    assert all(len(c) <= 1000 for c in chunks)
    assert sum(len(c) for c in chunks) >= 5000  # overlap means >= original


def test_content_hash_deterministic():
    assert content_hash(b"abc") == content_hash(b"abc")
    assert content_hash(b"abc") != content_hash(b"abd")


# ── KnowledgeAgent ────────────────────────────────────────────────────────────

@pytest.fixture
def mock_ollama():
    svc = MagicMock()
    svc.embed = AsyncMock(return_value=[0.1] * 768)
    svc.chat = AsyncMock(return_value={
        "content": "The answer is 42 [1].", "model": "test", "tokens_used": 30,
    })
    return svc


@pytest.fixture
def mock_qdrant():
    q = MagicMock()
    q.upsert = AsyncMock(return_value="point-id")
    q.search = AsyncMock(return_value=[])
    return q


@pytest.fixture
def agent(mock_ollama, mock_qdrant, mock_settings):
    return KnowledgeAgent(ollama=mock_ollama, qdrant=mock_qdrant)


@pytest_asyncio.fixture
async def kb_user(db_session):
    user = User(phone_number="18885550000", role="user")
    db_session.add(user)
    await db_session.flush()
    return user


@pytest.mark.asyncio
async def test_ingest_note_creates_item_and_embeds(agent, mock_qdrant, db_session, kb_user):
    result = await agent.handle_command(
        db_session, kb_user.id, "knowledge_ingest",
        "remember this: the wifi password at the office is hunter2",
    )
    assert "Ingested" in result

    item = (await db_session.execute(
        select(KnowledgeItem).where(KnowledgeItem.user_id == kb_user.id)
    )).scalar_one()
    assert item.status == "ready"
    assert item.chunk_count == 1
    mock_qdrant.upsert.assert_awaited()
    payload = mock_qdrant.upsert.await_args.kwargs["payload"]
    assert payload["user_id"] == str(kb_user.id)
    assert "hunter2" in payload["text"]


@pytest.mark.asyncio
async def test_ingest_duplicate_detected_by_hash(agent, db_session, kb_user):
    text = "remember this exact note"
    await agent.ingest_note(db_session, kb_user.id, text)
    result = await agent.ingest_note(db_session, kb_user.id, text)
    assert "Already in your knowledge base" in result

    items = (await db_session.execute(
        select(KnowledgeItem).where(KnowledgeItem.user_id == kb_user.id)
    )).scalars().all()
    assert len(items) == 1


@pytest.mark.asyncio
async def test_ingest_document_pdf_like_flow(agent, mock_qdrant, db_session, kb_user):
    data = ("Chapter 1.\n\n" + "content " * 300).encode()
    result = await agent.ingest_document(
        db_session, kb_user.id, data=data, filename="handbook.txt", title="Handbook"
    )
    assert "Ingested" in result
    assert "Handbook" in result
    item = (await db_session.execute(
        select(KnowledgeItem).where(KnowledgeItem.user_id == kb_user.id)
    )).scalar_one()
    assert item.chunk_count >= 2
    assert mock_qdrant.upsert.await_count == item.chunk_count


@pytest.mark.asyncio
async def test_ingest_embedding_failure_marks_failed(agent, mock_ollama, db_session, kb_user):
    mock_ollama.embed = AsyncMock(side_effect=RuntimeError("ollama down"))
    result = await agent.ingest_note(db_session, kb_user.id, "some note")
    assert "failed" in result.lower()
    item = (await db_session.execute(
        select(KnowledgeItem).where(KnowledgeItem.user_id == kb_user.id)
    )).scalar_one()
    assert item.status == "failed"


@pytest.mark.asyncio
async def test_answer_no_results(agent, db_session, kb_user):
    result = await agent.handle_command(
        db_session, kb_user.id, "knowledge_search", "what is the wifi password?"
    )
    assert "don't have anything" in result.lower()


@pytest.mark.asyncio
async def test_answer_with_rag_context(agent, mock_ollama, mock_qdrant, db_session, kb_user):
    mock_qdrant.search = AsyncMock(return_value=[
        {"score": 0.9, "title": "Office Notes", "source_type": "note",
         "text": "The wifi password is hunter2."},
    ])
    result = await agent.handle_command(
        db_session, kb_user.id, "knowledge_search", "what is the wifi password?"
    )
    assert "42" in result  # mocked LLM answer
    assert "Office Notes" in result  # source citation
    # The RAG prompt must contain the retrieved chunk
    prompt = mock_ollama.chat.await_args.kwargs["messages"][0]["content"]
    assert "hunter2" in prompt


@pytest.mark.asyncio
async def test_qdrant_error_returns_friendly_message(agent, mock_qdrant, db_session, kb_user):
    mock_qdrant.search = AsyncMock(side_effect=RuntimeError("qdrant unreachable"))
    result = await agent.handle_command(
        db_session, kb_user.id, "knowledge_search", "anything"
    )
    assert "⚠️" in result
