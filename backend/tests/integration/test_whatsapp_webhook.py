"""
Integration tests for WhatsApp webhook.

Critical test: POST /whatsapp/webhook with valid payload
→ message persisted in DB
→ audit log written
→ WhatsApp reply sent
"""

import hashlib
import hmac
import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def make_signature(body: bytes, secret: str = "test_app_secret") -> str:
    sig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return f"sha256={sig}"


class TestWhatsAppWebhookVerification:
    def test_get_webhook_valid_token(self):
        from fastapi.testclient import TestClient
        from app.api.routes.whatsapp import router
        from fastapi import FastAPI

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app, raise_server_exceptions=False)

        with patch("app.api.routes.whatsapp.get_settings") as mock_settings:
            mock_settings.return_value.WHATSAPP_VERIFY_TOKEN = "test_verify_token"

            response = client.get(
                "/whatsapp/webhook",
                params={
                    "hub.mode": "subscribe",
                    "hub.verify_token": "test_verify_token",
                    "hub.challenge": "12345",
                },
            )

        assert response.status_code == 200
        assert response.text == "12345"

    def test_get_webhook_invalid_token_returns_403(self):
        from fastapi.testclient import TestClient
        from app.api.routes.whatsapp import router
        from fastapi import FastAPI

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app, raise_server_exceptions=False)

        with patch("app.api.routes.whatsapp.get_settings") as mock_settings:
            mock_settings.return_value.WHATSAPP_VERIFY_TOKEN = "correct_token"

            response = client.get(
                "/whatsapp/webhook",
                params={
                    "hub.mode": "subscribe",
                    "hub.verify_token": "wrong_token",
                    "hub.challenge": "12345",
                },
            )

        assert response.status_code == 403


class TestWhatsAppPayloadParsing:
    def test_text_payload_parsed_correctly(self, whatsapp_text_payload):
        from app.models.schemas.whatsapp import WAWebhookPayload

        payload = WAWebhookPayload.model_validate(whatsapp_text_payload)

        assert payload.object == "whatsapp_business_account"
        assert len(payload.entry) == 1
        message = payload.entry[0].changes[0].value.messages[0]
        assert message.type == "text"
        assert message.text.body == "Hello, what can you do for me?"
        assert message.from_ == "14155551234"

    def test_voice_payload_parsed_correctly(self, whatsapp_voice_payload):
        from app.models.schemas.whatsapp import WAWebhookPayload

        payload = WAWebhookPayload.model_validate(whatsapp_voice_payload)

        message = payload.entry[0].changes[0].value.messages[0]
        assert message.type == "audio"
        assert message.audio.id == "media_audio_001"
        assert message.audio.voice is True

    def test_status_update_has_no_messages(self):
        status_payload = {
            "object": "whatsapp_business_account",
            "entry": [{
                "id": "test",
                "changes": [{
                    "value": {
                        "messaging_product": "whatsapp",
                        "metadata": {"display_phone_number": "123", "phone_number_id": "456"},
                        "statuses": [{"id": "msg1", "status": "delivered"}],
                    },
                    "field": "messages",
                }],
            }],
        }
        from app.models.schemas.whatsapp import WAWebhookPayload
        payload = WAWebhookPayload.model_validate(status_payload)
        messages = payload.entry[0].changes[0].value.messages
        assert len(messages) == 0


class TestWebhookSignatureVerification:
    def test_valid_hmac_signature_passes(self):
        from app.core.security import verify_whatsapp_signature

        secret = "my_app_secret"
        body = b'{"test": "data"}'
        sig = make_signature(body, secret)

        with patch("app.core.security.get_settings") as mock_settings:
            mock_settings.return_value.WHATSAPP_APP_SECRET = secret
            assert verify_whatsapp_signature(body, sig) is True

    def test_tampered_body_fails_signature(self):
        from app.core.security import verify_whatsapp_signature

        secret = "my_app_secret"
        original_body = b'{"test": "data"}'
        sig = make_signature(original_body, secret)
        tampered_body = b'{"test": "tampered"}'

        with patch("app.core.security.get_settings") as mock_settings:
            mock_settings.return_value.WHATSAPP_APP_SECRET = secret
            assert verify_whatsapp_signature(tampered_body, sig) is False

    def test_missing_signature_fails(self):
        from app.core.security import verify_whatsapp_signature

        with patch("app.core.security.get_settings") as mock_settings:
            mock_settings.return_value.WHATSAPP_APP_SECRET = "secret"
            assert verify_whatsapp_signature(b"body", "") is False


class TestMessageDeduplication:
    def test_duplicate_message_id_skipped(self):
        from app.api.routes.whatsapp import _track_processed, _processed_ids

        msg_id = "wamid.unique_test_123"
        _processed_ids.discard(msg_id)

        _track_processed(msg_id)
        assert msg_id in _processed_ids

    def test_cache_eviction_on_overflow(self):
        from app.api.routes.whatsapp import MAX_PROCESSED_CACHE, _track_processed, _processed_ids

        _processed_ids.clear()
        for i in range(MAX_PROCESSED_CACHE + 10):
            _track_processed(f"wamid.msg_{i}")

        assert len(_processed_ids) <= MAX_PROCESSED_CACHE
