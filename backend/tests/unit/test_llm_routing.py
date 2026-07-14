"""Unit tests for local/cloud LLM routing in OllamaService."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.ollama import OllamaService


@pytest.fixture
def service(mock_settings):
    with patch("app.services.ollama.ollama.AsyncClient") as mock_client_cls:
        svc = OllamaService()
        svc._mock_client = mock_client_cls.return_value
        yield svc


@pytest.mark.asyncio
async def test_plain_model_uses_ollama(service):
    response = MagicMock()
    response.message.content = "local reply"
    response.model = "qwen3:latest"
    response.prompt_eval_count = 10
    response.eval_count = 20
    service._client.chat = AsyncMock(return_value=response)

    result = await service.chat([{"role": "user", "content": "hi"}], model="qwen3:latest")

    assert result["content"] == "local reply"
    assert result["tokens_used"] == 30
    service._client.chat.assert_awaited_once()


@pytest.mark.asyncio
async def test_cloud_prefix_requires_api_key(service, monkeypatch):
    monkeypatch.delenv("CLOUD_LLM_API_KEY", raising=False)
    service._settings = MagicMock()
    service._settings.CLOUD_LLM_API_KEY = None

    with pytest.raises(RuntimeError, match="CLOUD_LLM_API_KEY"):
        await service.chat([{"role": "user", "content": "hi"}], model="cloud:glm-4.5-flash")


@pytest.mark.asyncio
async def test_cloud_prefix_calls_openai_compatible_api(service):
    service._settings = MagicMock()
    service._settings.CLOUD_LLM_API_KEY = "zai-test-key"
    service._settings.CLOUD_LLM_API_BASE = "https://api.z.ai/api/paas/v4"
    service._settings.OLLAMA_TIMEOUT = 120

    fake_response = MagicMock()
    fake_response.raise_for_status = MagicMock()
    fake_response.json.return_value = {
        "choices": [{"message": {"content": "cloud reply"}}],
        "model": "glm-4.5-flash",
        "usage": {"total_tokens": 42},
    }

    mock_http = MagicMock()
    mock_http.post = AsyncMock(return_value=fake_response)
    mock_http.__aenter__ = AsyncMock(return_value=mock_http)
    mock_http.__aexit__ = AsyncMock(return_value=False)

    ollama_chat = AsyncMock()
    service._client.chat = ollama_chat

    with patch("app.services.ollama.httpx.AsyncClient", return_value=mock_http):
        result = await service.chat(
            [{"role": "user", "content": "hi"}],
            model="cloud:glm-4.5-flash",
            temperature=0.2,
            max_tokens=100,
        )

    assert result["content"] == "cloud reply"
    assert result["model"] == "glm-4.5-flash"
    assert result["tokens_used"] == 42
    ollama_chat.assert_not_awaited()  # never touched local Ollama

    url = mock_http.post.await_args.args[0]
    assert url == "https://api.z.ai/api/paas/v4/chat/completions"
    payload = mock_http.post.await_args.kwargs["json"]
    assert payload["model"] == "glm-4.5-flash"  # prefix stripped
    assert payload["temperature"] == 0.2
    assert payload["max_tokens"] == 100
    headers = mock_http.post.await_args.kwargs["headers"]
    assert headers["Authorization"] == "Bearer zai-test-key"


@pytest.mark.asyncio
async def test_cloud_embedding_rejected(service):
    with pytest.raises(ValueError, match="stay local"):
        await service.embed("some text", model="cloud:embedding-3")
