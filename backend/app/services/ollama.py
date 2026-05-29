from typing import Any

import ollama
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class OllamaService:
    def __init__(self) -> None:
        settings = get_settings()
        self._client = ollama.AsyncClient(host=settings.OLLAMA_BASE_URL)
        self._settings = settings

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    async def chat(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> dict[str, Any]:
        model = model or self._settings.OLLAMA_DEFAULT_MODEL
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

    async def embed(self, text: str, model: str | None = None) -> list[float]:
        model = model or self._settings.OLLAMA_EMBEDDING_MODEL
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
