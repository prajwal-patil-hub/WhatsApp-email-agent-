import httpx

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class WhatsAppService:
    def __init__(self) -> None:
        self._settings = get_settings()

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._settings.WHATSAPP_API_TOKEN}",
            "Content-Type": "application/json",
        }

    async def send_text(self, to: str, body: str) -> dict:
        url = (
            f"{self._settings.whatsapp_api_url}"
            f"/{self._settings.WHATSAPP_PHONE_NUMBER_ID}/messages"
        )
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "text",
            "text": {"body": body, "preview_url": False},
        }
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(url, json=payload, headers=self._headers())
            resp.raise_for_status()
            data = resp.json()
            logger.info(
                "whatsapp_message_sent",
                to=to,
                message_id=data.get("messages", [{}])[0].get("id"),
            )
            return data

    async def send_typing_indicator(self, to: str) -> None:
        """Marks the conversation as 'typing' to show the user a response is coming."""
        url = (
            f"{self._settings.whatsapp_api_url}"
            f"/{self._settings.WHATSAPP_PHONE_NUMBER_ID}/messages"
        )
        payload = {
            "messaging_product": "whatsapp",
            "status": "read",
            "message_id": "placeholder",
        }
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                await client.post(url, json=payload, headers=self._headers())
        except Exception:
            pass  # typing indicator failure is non-fatal

    async def get_media_url(self, media_id: str) -> str:
        url = f"{self._settings.whatsapp_api_url}/{media_id}"
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(url, headers=self._headers())
            resp.raise_for_status()
            return resp.json()["url"]

    async def download_media(self, media_url: str) -> bytes:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.get(media_url, headers=self._headers())
            resp.raise_for_status()
            return resp.content


_whatsapp_service: WhatsAppService | None = None


def get_whatsapp_service() -> WhatsAppService:
    global _whatsapp_service
    if _whatsapp_service is None:
        _whatsapp_service = WhatsAppService()
    return _whatsapp_service
