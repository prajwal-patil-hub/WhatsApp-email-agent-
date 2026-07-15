"""Edge TTS service — converts text to speech audio. Phase 3 feature."""

import tempfile
from pathlib import Path

from app.core.logging import get_logger

logger = get_logger(__name__)


async def text_to_speech(
    text: str,
    voice: str = "en-US-JennyNeural",
    output_format: str = "audio-24khz-48kbitrate-mono-mp3",
) -> bytes:
    import edge_tts

    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
        tmp_path = tmp.name

    communicator = edge_tts.Communicate(text, voice)
    await communicator.save(tmp_path)

    audio_bytes = Path(tmp_path).read_bytes()
    Path(tmp_path).unlink(missing_ok=True)

    logger.info("edge_tts_generated", text_length=len(text), voice=voice, bytes=len(audio_bytes))
    return audio_bytes


AVAILABLE_VOICES = [
    "en-US-JennyNeural",
    "en-US-GuyNeural",
    "en-GB-SoniaNeural",
    "en-IN-NeerjaNeural",
]
