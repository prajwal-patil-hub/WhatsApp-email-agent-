import os
import tempfile
from pathlib import Path

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_whisper_model = None


def _get_model():
    global _whisper_model
    if _whisper_model is None:
        from faster_whisper import WhisperModel

        settings = get_settings()
        logger.info(
            "loading_whisper_model",
            size=settings.WHISPER_MODEL_SIZE,
            device=settings.WHISPER_DEVICE,
        )
        _whisper_model = WhisperModel(
            settings.WHISPER_MODEL_SIZE,
            device=settings.WHISPER_DEVICE,
            compute_type=settings.WHISPER_COMPUTE_TYPE,
        )
    return _whisper_model


async def transcribe_audio(audio_bytes: bytes, mime_type: str = "audio/ogg") -> str:
    suffix = _mime_to_suffix(mime_type)
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(audio_bytes)
        tmp_path = tmp.name

    try:
        return _transcribe_file(tmp_path)
    finally:
        os.unlink(tmp_path)


async def transcribe_file(file_path: str | Path) -> str:
    return _transcribe_file(str(file_path))


def _transcribe_file(file_path: str) -> str:
    model = _get_model()
    segments, info = model.transcribe(
        file_path,
        beam_size=5,
        vad_filter=True,
        vad_parameters={"min_silence_duration_ms": 500},
    )
    text = " ".join(segment.text.strip() for segment in segments)
    logger.info(
        "whisper_transcription_complete",
        duration_seconds=round(info.duration, 2),
        language=info.language,
        language_probability=round(info.language_probability, 3),
        text_length=len(text),
    )
    return text.strip()


def _mime_to_suffix(mime_type: str) -> str:
    mapping = {
        "audio/ogg": ".ogg",
        "audio/mpeg": ".mp3",
        "audio/mp4": ".m4a",
        "audio/wav": ".wav",
        "audio/webm": ".webm",
    }
    for key, suffix in mapping.items():
        if key in mime_type:
            return suffix
    return ".ogg"


def warmup_whisper() -> None:
    """Pre-load the Whisper model at startup to avoid cold-start latency."""
    try:
        _get_model()
        logger.info("whisper_model_warmed_up")
    except Exception as exc:
        logger.warning("whisper_warmup_failed", error=str(exc))
