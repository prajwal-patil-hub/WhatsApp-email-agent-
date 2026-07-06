"""
WhatsApp webhook handler — the primary entry point for all user interactions.

GET  /whatsapp/webhook  — Meta verification challenge
POST /whatsapp/webhook  — Incoming message processing
POST /whatsapp/voice    — Voice note transcription + processing
"""

import time

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, Request, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.coordinator import ExecutiveCoordinator
from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.security import verify_whatsapp_signature
from app.models.db.conversation import Conversation
from app.models.db.message import Message
from app.models.db.user import User
from app.models.schemas.whatsapp import WAWebhookPayload
from app.services import audit
from app.services.ollama import get_ollama_service
from app.services.whatsapp import get_whatsapp_service
from app.services.whisper import transcribe_audio

router = APIRouter(prefix="/whatsapp", tags=["whatsapp"])
logger = get_logger(__name__)

_processed_ids: set[str] = set()  # in-memory dedup (replace with Redis in prod)
MAX_PROCESSED_CACHE = 10_000


@router.get("/webhook")
async def verify_webhook(request: Request) -> int:
    settings = get_settings()
    params = request.query_params
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")

    if mode == "subscribe" and token == settings.WHATSAPP_VERIFY_TOKEN:
        logger.info("whatsapp_webhook_verified")
        return int(challenge)

    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Verification failed")


@router.post("/webhook", status_code=status.HTTP_200_OK)
async def receive_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
) -> dict:
    body = await request.body()
    signature = request.headers.get("X-Hub-Signature-256", "")

    if not verify_whatsapp_signature(body, signature):
        logger.warning("whatsapp_signature_invalid")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid signature")

    try:
        payload = WAWebhookPayload.model_validate_json(body)
    except Exception as exc:
        logger.warning("whatsapp_payload_parse_error", error=str(exc))
        return {"status": "ok"}

    for entry in payload.entry:
        for change in entry.changes:
            if change.field != "messages":
                continue
            for wa_msg in change.value.messages:
                if wa_msg.id in _processed_ids:
                    logger.debug("whatsapp_duplicate_message", wa_message_id=wa_msg.id)
                    continue
                _track_processed(wa_msg.id)

                contact = next(
                    (c for c in change.value.contacts if c.wa_id == wa_msg.from_),
                    None,
                )
                background_tasks.add_task(
                    _process_message,
                    wa_message_id=wa_msg.id,
                    phone_number=wa_msg.from_,
                    contact_name=contact.profile.get("name") if contact else None,
                    message_type=wa_msg.type,
                    text_content=wa_msg.text.body if wa_msg.text else None,
                    audio_id=wa_msg.audio.id if wa_msg.audio else None,
                    audio_mime=wa_msg.audio.mime_type if wa_msg.audio else None,
                    timestamp=wa_msg.timestamp,
                )

    return {"status": "ok"}


@router.post("/voice")
async def receive_voice(
    background_tasks: BackgroundTasks,
    audio: UploadFile = File(...),
    phone_number: str = Form(...),
    wa_message_id: str = Form(...),
    mime_type: str = Form(default="audio/ogg"),
) -> dict:
    audio_bytes = await audio.read()
    transcription = await transcribe_audio(audio_bytes, mime_type)
    logger.info("voice_note_transcribed", phone_number=phone_number, length=len(transcription))

    background_tasks.add_task(
        _process_message,
        wa_message_id=wa_message_id,
        phone_number=phone_number,
        contact_name=None,
        message_type="voice",
        text_content=f"[Voice Note]: {transcription}",
        audio_id=None,
        audio_mime=None,
        timestamp=str(int(time.time())),
    )
    return {"transcription": transcription, "status": "processing"}


async def _process_message(
    wa_message_id: str,
    phone_number: str,
    contact_name: str | None,
    message_type: str,
    text_content: str | None,
    audio_id: str | None,
    audio_mime: str | None,
    timestamp: str,
) -> None:
    start = time.monotonic()
    settings = get_settings()
    whatsapp = get_whatsapp_service()
    ollama = get_ollama_service()

    # Background tasks MUST create their own DB session — the request-scoped session is closed.
    from app.core.database import get_session_factory

    async with get_session_factory()() as db:
        await _process_message_with_db(
            db=db,
            wa_message_id=wa_message_id,
            phone_number=phone_number,
            contact_name=contact_name,
            message_type=message_type,
            text_content=text_content,
            audio_id=audio_id,
            audio_mime=audio_mime,
            timestamp=timestamp,
            start=start,
            settings=settings,
            whatsapp=whatsapp,
            ollama=ollama,
        )


async def _process_message_with_db(
    db: AsyncSession,
    wa_message_id: str,
    phone_number: str,
    contact_name: str | None,
    message_type: str,
    text_content: str | None,
    audio_id: str | None,
    audio_mime: str | None,
    timestamp: str,
    start: float,
    settings,
    whatsapp,
    ollama,
) -> None:
    try:
        # Handle audio via WhatsApp API download + transcription
        if message_type in ("audio",) and audio_id and not text_content:
            try:
                media_url = await whatsapp.get_media_url(audio_id)
                audio_bytes = await whatsapp.download_media(media_url)
                transcription = await transcribe_audio(audio_bytes, audio_mime or "audio/ogg")
                text_content = f"[Voice Note]: {transcription}"
            except Exception as exc:
                logger.error("voice_download_failed", error=str(exc))
                text_content = "[Voice note received but could not be transcribed]"

        if not text_content:
            logger.info("whatsapp_unsupported_message_type", message_type=message_type)
            await whatsapp.send_text(
                phone_number,
                "I received your message but can't process that type yet. Please send text or voice notes.",
            )
            return

        # Upsert user
        result = await db.execute(select(User).where(User.phone_number == phone_number))
        user = result.scalar_one_or_none()
        if not user:
            user = User(
                phone_number=phone_number,
                name=contact_name,
                role="admin" if phone_number == settings.ADMIN_PHONE_NUMBER else "user",
            )
            db.add(user)
            await db.flush()

        # Get or create active conversation
        conv_result = await db.execute(
            select(Conversation)
            .where(
                Conversation.user_id == user.id,
                Conversation.channel == "whatsapp",
                Conversation.status == "active",
            )
            .order_by(Conversation.updated_at.desc())
            .limit(1)
        )
        conversation = conv_result.scalar_one_or_none()
        if not conversation:
            conversation = Conversation(user_id=user.id, channel="whatsapp")
            db.add(conversation)
            await db.flush()

        # Persist user message
        user_msg = Message(
            conversation_id=conversation.id,
            role="user",
            content=text_content,
            message_type=message_type,
            wa_message_id=wa_message_id,
        )
        db.add(user_msg)
        await db.flush()

        # Process via coordinator
        coordinator = ExecutiveCoordinator(ollama)
        response = await coordinator.process(
            db=db,
            conversation_id=conversation.id,
            user_id=user.id,
            message=text_content,
        )

        # Persist assistant response
        assistant_msg = Message(
            conversation_id=conversation.id,
            role="assistant",
            content=response.content,
            message_type="text",
            tokens_used=response.tokens_used,
            model_used=response.model_used,
            processing_ms=response.processing_ms,
            metadata_={"intent": response.intent, "routed_to": response.routed_to},
        )
        db.add(assistant_msg)

        await audit.log_action(
            db,
            action="coordinator.process",
            user_id=user.id,
            resource_type="message",
            resource_id=str(user_msg.id),
            details={
                "intent": response.intent,
                "routed_to": response.routed_to,
                "processing_ms": response.processing_ms,
            },
            duration_ms=int((time.monotonic() - start) * 1000),
        )

        await db.commit()

        # Send WhatsApp reply
        await whatsapp.send_text(phone_number, response.content)

    except Exception as exc:
        logger.error("message_processing_failed", error=str(exc), phone_number=phone_number)
        await db.rollback()
        try:
            await whatsapp.send_text(
                phone_number,
                "I encountered an issue processing your message. Please try again in a moment.",
            )
        except Exception:
            pass


def _track_processed(wa_message_id: str) -> None:
    _processed_ids.add(wa_message_id)
    if len(_processed_ids) > MAX_PROCESSED_CACHE:
        # Evict half in place — rebinding would orphan other references to this set
        items = list(_processed_ids)
        _processed_ids.clear()
        _processed_ids.update(items[MAX_PROCESSED_CACHE // 2:])
