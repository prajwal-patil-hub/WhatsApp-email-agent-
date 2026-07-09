"""Unit tests for ExecutiveCoordinator."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.coordinator import ExecutiveCoordinator
from app.services.ollama import OllamaService


@pytest.fixture
def mock_ollama_service():
    service = MagicMock(spec=OllamaService)
    service.chat = AsyncMock(return_value={
        "content": "Hello! I'm your AI Chief of Staff.",
        "model": "qwen3:latest",
        "tokens_used": 42,
    })
    return service


@pytest.fixture
def coordinator(mock_ollama_service):
    return ExecutiveCoordinator(ollama=mock_ollama_service)


class TestIntentClassification:
    @pytest.mark.asyncio
    async def test_general_chat_intent(self, coordinator, mock_ollama_service):
        mock_ollama_service.chat = AsyncMock(return_value={
            "content": "general_chat",
            "model": "mistral:latest",
            "tokens_used": 5,
        })
        intent = await coordinator._classify_intent("How are you today?")
        assert intent == "general_chat"

    @pytest.mark.asyncio
    async def test_email_read_intent(self, coordinator, mock_ollama_service):
        mock_ollama_service.chat = AsyncMock(return_value={
            "content": "email_read",
            "model": "mistral:latest",
            "tokens_used": 5,
        })
        intent = await coordinator._classify_intent("Show me my unread emails")
        assert intent == "email_read"

    @pytest.mark.asyncio
    async def test_task_create_intent(self, coordinator, mock_ollama_service):
        mock_ollama_service.chat = AsyncMock(return_value={
            "content": "task_create",
            "model": "mistral:latest",
            "tokens_used": 5,
        })
        intent = await coordinator._classify_intent("Create a task to renew my passport by Friday")
        assert intent == "task_create"

    @pytest.mark.asyncio
    async def test_invalid_intent_falls_back_to_general_chat(self, coordinator, mock_ollama_service):
        mock_ollama_service.chat = AsyncMock(return_value={
            "content": "some_unknown_intent_xyz",
            "model": "mistral:latest",
            "tokens_used": 5,
        })
        intent = await coordinator._classify_intent("something random")
        assert intent == "general_chat"

    @pytest.mark.asyncio
    async def test_classification_error_falls_back(self, coordinator, mock_ollama_service):
        mock_ollama_service.chat = AsyncMock(side_effect=Exception("Ollama unavailable"))
        intent = await coordinator._classify_intent("anything")
        assert intent == "general_chat"


class TestRoutingStubs:
    @pytest.mark.asyncio
    async def test_email_route_delegates_to_email_agent(self, coordinator):
        from unittest.mock import AsyncMock, patch
        with patch.object(
            coordinator._email_agent, "handle_command", new_callable=AsyncMock
        ) as mock_handle:
            mock_handle.return_value = "email agent response"
            import uuid as _uuid
            response = await coordinator._route_email(
                None, _uuid.uuid4(), "email_read", "show emails"
            )
        assert response == "email agent response"
        mock_handle.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_task_route_delegates_to_task_agent(self, coordinator):
        from unittest.mock import AsyncMock, patch
        with patch.object(
            coordinator._task_agent, "handle_command", new_callable=AsyncMock
        ) as mock_handle:
            mock_handle.return_value = "task agent response"
            import uuid as _uuid
            response = await coordinator._route_task(
                None, _uuid.uuid4(), "task_create", "create task"
            )
        assert response == "task agent response"
        mock_handle.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_research_route_returns_phase5_message(self, coordinator):
        response = await coordinator._route_research("research AI agents")
        assert "Phase 5" in response

    @pytest.mark.asyncio
    async def test_calendar_route_returns_phase4_message(self, coordinator):
        response = await coordinator._route_calendar("calendar_schedule", "schedule meeting")
        assert "Phase 4" in response

    @pytest.mark.asyncio
    async def test_knowledge_route_returns_phase4_message(self, coordinator):
        response = await coordinator._route_knowledge("knowledge_search", "find my notes")
        assert "Phase 4" in response


class TestChatResponse:
    @pytest.mark.asyncio
    async def test_chat_response_uses_history(self, coordinator, mock_ollama_service):
        conversation_id = uuid.uuid4()

        with patch("app.memory.short_term.get_context", new_callable=AsyncMock) as mock_get, \
             patch("app.memory.short_term.add_message", new_callable=AsyncMock):
            mock_get.return_value = [
                {"role": "user", "content": "My name is Prajwal"},
                {"role": "assistant", "content": "Nice to meet you, Prajwal!"},
            ]
            mock_ollama_service.chat = AsyncMock(return_value={
                "content": "You mentioned your name is Prajwal.",
                "model": "qwen3:latest",
                "tokens_used": 30,
            })

            text, model, tokens = await coordinator._chat_response(
                conversation_id, "What is my name?", None
            )
            assert text == "You mentioned your name is Prajwal."
            assert tokens == 30

            call_args = mock_ollama_service.chat.call_args
            messages = call_args.kwargs["messages"]
            assert any(m["role"] == "system" for m in messages)
            assert any(m["content"] == "My name is Prajwal" for m in messages)

    @pytest.mark.asyncio
    async def test_chat_response_injects_extra_context(self, coordinator, mock_ollama_service):
        conversation_id = uuid.uuid4()
        with patch("app.memory.short_term.get_context", new_callable=AsyncMock) as mock_get, \
             patch("app.memory.short_term.add_message", new_callable=AsyncMock):
            mock_get.return_value = []
            mock_ollama_service.chat = AsyncMock(return_value={
                "content": "Response",
                "model": "qwen3:latest",
                "tokens_used": 10,
            })

            await coordinator._chat_response(
                conversation_id, "Hello", "Extra system context here"
            )

            call_args = mock_ollama_service.chat.call_args
            messages = call_args.kwargs["messages"]
            system_messages = [m for m in messages if m["role"] == "system"]
            assert len(system_messages) == 2
            assert any("Extra system context" in m["content"] for m in system_messages)
