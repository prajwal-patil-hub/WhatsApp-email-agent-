"""LLM service — local Ollama by default, optional OpenAI-compatible cloud.

Any model name prefixed with "cloud:" (e.g. "cloud:glm-4.5-flash") is routed
to CLOUD_LLM_API_BASE with CLOUD_LLM_API_KEY instead of Ollama. This lets
each role (default/fast/reasoning) independently run local or cloud via
nothing but .env — agents never know the difference.

Embeddings always stay local: Qdrant collections are built for
nomic-embed-text's 768-dim vectors.
"""

from typing import Any

import httpx
import ollama
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

CLOUD_PREFIX = "cloud:"


class OllamaService:
    def __init__(self) -> None:
        settings = get_settings()
        self._client = ollama.AsyncClient(host=settings.OLLAMA_BASE_URL)
        self._settings = settings

    async def chat(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> dict[str, Any]:
        """Dispatcher — config errors fail fast; only network calls retry."""
        model = model or self._settings.OLLAMA_DEFAULT_MODEL

        if model.startswith(CLOUD_PREFIX):
            if not self._settings.CLOUD_LLM_API_KEY:
                raise RuntimeError(
                    f"Model '{model}' requires CLOUD_LLM_API_KEY in .env "
                    "(and CLOUD_LLM_API_BASE if not using the Z.ai default)."
                )
            return await self._chat_cloud(
                model.removeprefix(CLOUD_PREFIX), messages, temperature, max_tokens
            )
        return await self._chat_ollama(model, messages, temperature, max_tokens)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    async def _chat_ollama(
        self,
        model: str,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: int | None,
    ) -> dict[str, Any]:
        options: dict[str, Any] = {"temperature": temperature}
        if max_tokens:
            options["num_predict"] = max_tokens

        logger.debug("ollama_chat_request", model=model, message_count=len(messages))
        response = await self._client.chat(
            model=model,
            messages=messages,
            options=options,
        )
        return {
            "content": response.message.content,
            "model": response.model,
            "tokens_used": (response.prompt_eval_count or 0) + (response.eval_count or 0),
        }

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    async def _chat_cloud(
        self,
        model: str,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: int | None,
    ) -> dict[str, Any]:
        """OpenAI-compatible chat completions (Z.ai GLM, Groq, OpenRouter, ...)."""
        settings = self._settings

        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }
        if max_tokens:
            payload["max_tokens"] = max_tokens

        logger.debug("cloud_chat_request", model=model, message_count=len(messages))
        async with httpx.AsyncClient(timeout=settings.OLLAMA_TIMEOUT) as client:
            resp = await client.post(
                f"{settings.CLOUD_LLM_API_BASE.rstrip('/')}/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.CLOUD_LLM_API_KEY}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()

        return {
            "content": data["choices"][0]["message"]["content"],
            "model": data.get("model", model),
            "tokens_used": data.get("usage", {}).get("total_tokens", 0),
        }

    async def embed(self, text: str, model: str | None = None) -> list[float]:
        model = model or self._settings.OLLAMA_EMBEDDING_MODEL
        if model.startswith(CLOUD_PREFIX):
            raise ValueError(
                "Embeddings must stay local — Qdrant collections are sized for "
                "nomic-embed-text (768 dims). Remove the cloud: prefix from "
                "OLLAMA_EMBEDDING_MODEL."
            )
        response = await self._client.embed(model=model, input=text)
        return response.embeddings[0]

    async def is_available(self) -> bool:
        try:
            await self._client.list()
            return True
        except Exception:
            return False

    async def list_models(self) -> list[str]:
        try:
            response = await self._client.list()
            return [m.model for m in response.models]
        except Exception:
            return []


_ollama_service: OllamaService | None = None


def get_ollama_service() -> OllamaService:
    global _ollama_service
    if _ollama_service is None:
        _ollama_service = OllamaService()
    return _ollama_service
