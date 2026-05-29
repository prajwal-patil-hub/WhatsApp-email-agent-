"""Unit tests for Whisper voice transcription service."""

import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestWhisperService:
    def test_mime_to_suffix_ogg(self):
        from app.services.whisper import _mime_to_suffix
        assert _mime_to_suffix("audio/ogg") == ".ogg"
        assert _mime_to_suffix("audio/ogg; codecs=opus") == ".ogg"

    def test_mime_to_suffix_mp3(self):
        from app.services.whisper import _mime_to_suffix
        assert _mime_to_suffix("audio/mpeg") == ".mp3"

    def test_mime_to_suffix_unknown_defaults_to_ogg(self):
        from app.services.whisper import _mime_to_suffix
        assert _mime_to_suffix("audio/unknown-format") == ".ogg"

    @pytest.mark.asyncio
    async def test_transcribe_audio_calls_model(self):
        mock_model = MagicMock()
        mock_segment = MagicMock()
        mock_segment.text = "Hello world"
        mock_info = MagicMock()
        mock_info.duration = 2.5
        mock_info.language = "en"
        mock_info.language_probability = 0.99
        mock_model.transcribe = MagicMock(return_value=([mock_segment], mock_info))

        with patch("app.services.whisper._get_model", return_value=mock_model):
            from app.services.whisper import transcribe_audio
            result = await transcribe_audio(b"fake_audio_bytes", "audio/ogg")

        assert result == "Hello world"
        mock_model.transcribe.assert_called_once()

    @pytest.mark.asyncio
    async def test_transcribe_multiple_segments_joined(self):
        mock_model = MagicMock()
        seg1 = MagicMock()
        seg1.text = " First segment"
        seg2 = MagicMock()
        seg2.text = " Second segment"
        mock_info = MagicMock()
        mock_info.duration = 5.0
        mock_info.language = "en"
        mock_info.language_probability = 0.95
        mock_model.transcribe = MagicMock(return_value=([seg1, seg2], mock_info))

        with patch("app.services.whisper._get_model", return_value=mock_model):
            from app.services.whisper import transcribe_audio
            result = await transcribe_audio(b"fake_audio", "audio/ogg")

        assert "First segment" in result
        assert "Second segment" in result

    @pytest.mark.asyncio
    async def test_transcribe_empty_audio_returns_empty_string(self):
        mock_model = MagicMock()
        mock_info = MagicMock()
        mock_info.duration = 0.1
        mock_info.language = "en"
        mock_info.language_probability = 0.1
        mock_model.transcribe = MagicMock(return_value=([], mock_info))

        with patch("app.services.whisper._get_model", return_value=mock_model):
            from app.services.whisper import transcribe_audio
            result = await transcribe_audio(b"", "audio/ogg")

        assert result == ""

    def test_warmup_whisper_handles_failure_gracefully(self):
        with patch("app.services.whisper._get_model", side_effect=Exception("Model load failed")):
            from app.services.whisper import warmup_whisper
            warmup_whisper()  # Should not raise


class TestSecurityFunctions:
    def test_verify_whatsapp_signature_valid(self):
        import hashlib
        import hmac
        from app.core.security import verify_whatsapp_signature

        secret = "test_secret"
        body = b'{"test": "payload"}'
        sig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()

        with patch("app.core.security.get_settings") as mock_settings:
            mock_settings.return_value.WHATSAPP_APP_SECRET = secret
            result = verify_whatsapp_signature(body, f"sha256={sig}")

        assert result is True

    def test_verify_whatsapp_signature_invalid(self):
        from app.core.security import verify_whatsapp_signature

        with patch("app.core.security.get_settings") as mock_settings:
            mock_settings.return_value.WHATSAPP_APP_SECRET = "real_secret"
            result = verify_whatsapp_signature(b"body", "sha256=invalidsig")

        assert result is False

    def test_verify_whatsapp_signature_missing_header(self):
        from app.core.security import verify_whatsapp_signature

        with patch("app.core.security.get_settings") as mock_settings:
            mock_settings.return_value.WHATSAPP_APP_SECRET = "secret"
            assert verify_whatsapp_signature(b"body", "") is False
            assert verify_whatsapp_signature(b"body", "malformed") is False

    def test_create_and_decode_token(self):
        from app.core.security import create_access_token, decode_token

        with patch("app.core.security.get_settings") as mock_settings:
            mock_settings.return_value.SECRET_KEY = "test_secret_at_least_32_chars_long!!"
            mock_settings.return_value.JWT_ALGORITHM = "HS256"
            mock_settings.return_value.JWT_ACCESS_TOKEN_EXPIRE_MINUTES = 60

            token = create_access_token("user-uuid-123", role="admin")
            payload = decode_token(token)

        assert payload["sub"] == "user-uuid-123"
        assert payload["role"] == "admin"
        assert "jti" in payload
        assert "exp" in payload

    def test_decode_invalid_token_raises(self):
        from app.core.security import decode_token

        with patch("app.core.security.get_settings") as mock_settings:
            mock_settings.return_value.SECRET_KEY = "test_secret"
            mock_settings.return_value.JWT_ALGORITHM = "HS256"
            with pytest.raises(ValueError, match="Invalid token"):
                decode_token("not.a.valid.token")
