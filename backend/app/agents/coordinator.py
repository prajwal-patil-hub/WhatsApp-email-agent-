"""
Executive Coordinator — Phase 1 complete implementation.

Responsibilities:
- Classify user intent
- Route to specialized agents (stubs in Phase 1, real in Phase 2+)
- Maintain conversation coherence via short-term memory
- Inject relevant long-term memories into context
- Return response + route metadata
"""

import time
import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.email_agent import EmailAgent
from app.agents.knowledge_agent import KnowledgeAgent
from app.agents.scheduling_agent import SchedulingAgent
from app.agents.task_agent import TaskAgent
from app.core.config import get_settings
from app.core.logging import get_logger
from app.memory import short_term
from app.services.ollama import OllamaService

logger = get_logger(__name__)

SYSTEM_PROMPT = """You are an intelligent personal AI Chief of Staff. You are highly capable, \
concise, and professional. You help manage communications, tasks, emails, calendar, research, \
and knowledge for your principal.

You are communicating via WhatsApp, so keep responses conversational and appropriately brief \
unless a detailed response is explicitly needed.

Current capabilities:
- General conversation and Q&A
- Email management — read inbox, draft replies, send emails (Gmail & Outlook)
- Task management — create, list, update, complete tasks with priorities, due dates, recurrence
- Calendar — schedule meetings, check your agenda (Google Calendar)
- Knowledge base — ingest documents/notes, answer questions from them (RAG)
- Remembering context within this conversation and long-term semantic memory

Coming soon:
- Research reports (Phase 5)

Always be helpful, proactive, and professional. If you cannot do something yet, say so clearly \
and suggest when it will be available."""

INTENT_CLASSIFIER_PROMPT = """Classify this message intent. Reply with ONLY one of these labels:
- general_chat
- email_read
- email_draft
- email_send
- task_create
- task_list
- task_update
- calendar_schedule
- calendar_query
- knowledge_search
- knowledge_ingest
- research
- memory_store
- memory_search
- briefing

Message: {message}"""


@dataclass
class CoordinatorResponse:
    content: str
    intent: str
    model_used: str
    tokens_used: int
    processing_ms: int
    routed_to: str | None = None
    metadata: dict[str, Any] | None = None


class ExecutiveCoordinator:
    def __init__(self, ollama: OllamaService) -> None:
        self._ollama = ollama
        self._settings = get_settings()
        self._email_agent = EmailAgent(ollama=ollama)
        self._task_agent = TaskAgent(ollama=ollama)
        self._scheduling_agent = SchedulingAgent(ollama=ollama)

    async def process(
        self,
        db: AsyncSession,
        conversation_id: uuid.UUID,
        user_id: uuid.UUID,
        message: str,
        system_context: str | None = None,
    ) -> CoordinatorResponse:
        start = time.monotonic()

        intent = await self._classify_intent(message)
        logger.info("intent_classified", intent=intent, user_id=str(user_id))

        routed_to = None
        response_text: str

        if intent in ("email_read", "email_draft", "email_send"):
            response_text = await self._route_email(db, user_id, intent, message)
            routed_to = "email_agent"
        elif intent in ("task_create", "task_list", "task_update"):
            response_text = await self._route_task(db, user_id, intent, message)
            routed_to = "task_agent"
        elif intent in ("calendar_schedule", "calendar_query"):
            response_text = await self._route_calendar(db, user_id, intent, message)
            routed_to = "scheduling_agent"
        elif intent in ("knowledge_search", "knowledge_ingest"):
            response_text = await self._route_knowledge(db, user_id, intent, message)
            routed_to = "knowledge_agent"
        elif intent == "research":
            response_text = await self._route_research(message)
            routed_to = "research_agent"
        elif intent in ("memory_store", "memory_search"):
            response_text = await self._handle_memory(db, user_id, intent, message)
        elif intent == "briefing":
            response_text = (
                "📋 *Daily Briefing* will be delivered automatically every morning at 7am! "
                "The morning briefing includes your calendar, priority emails, pending tasks, "
                "and project updates. (Full briefing agent active in Phase 7)"
            )
            routed_to = "briefing_agent"
        else:
            response_text, model, tokens = await self._chat_response(
                conversation_id, message, system_context
            )
            elapsed = int((time.monotonic() - start) * 1000)
            return CoordinatorResponse(
                content=response_text,
                intent=intent,
                model_used=model,
                tokens_used=tokens,
                processing_ms=elapsed,
                routed_to=None,
            )

        await short_term.add_message(conversation_id, "user", message)
        await short_term.add_message(conversation_id, "assistant", response_text)

        elapsed = int((time.monotonic() - start) * 1000)
        return CoordinatorResponse(
            content=response_text,
            intent=intent,
            model_used=self._settings.OLLAMA_FAST_MODEL,
            tokens_used=0,
            processing_ms=elapsed,
            routed_to=routed_to,
        )

    async def _classify_intent(self, message: str) -> str:
        try:
            result = await self._ollama.chat(
                messages=[
                    {
                        "role": "user",
                        "content": INTENT_CLASSIFIER_PROMPT.format(message=message),
                    }
                ],
                model=self._settings.OLLAMA_FAST_MODEL,
                temperature=0.0,
                max_tokens=20,
            )
            intent = result["content"].strip().lower().split()[0]
            valid = {
                "general_chat", "email_read", "email_draft", "email_send",
                "task_create", "task_list", "task_update", "calendar_schedule",
                "calendar_query", "knowledge_search", "knowledge_ingest",
                "research", "memory_store", "memory_search", "briefing",
            }
            return intent if intent in valid else "general_chat"
        except Exception as exc:
            logger.warning("intent_classification_failed", error=str(exc))
            return "general_chat"

    async def _chat_response(
        self,
        conversation_id: uuid.UUID,
        message: str,
        extra_context: str | None,
    ) -> tuple[str, str, int]:
        history = await short_term.get_context(conversation_id)
        messages: list[dict[str, str]] = [{"role": "system", "content": SYSTEM_PROMPT}]

        if extra_context:
            messages.append({"role": "system", "content": extra_context})

        messages.extend(history)
        messages.append({"role": "user", "content": message})

        result = await self._ollama.chat(
            messages=messages,
            model=self._settings.OLLAMA_DEFAULT_MODEL,
            temperature=0.7,
        )
        response_text = result["content"]

        await short_term.add_message(conversation_id, "user", message)
        await short_term.add_message(conversation_id, "assistant", response_text)

        return response_text, result["model"], result["tokens_used"]

    async def _route_email(
        self, db: AsyncSession, user_id: uuid.UUID, intent: str, message: str
    ) -> str:
        return await self._email_agent.handle_command(db, user_id, intent, message)

    async def _route_task(
        self, db: AsyncSession, user_id: uuid.UUID, intent: str, message: str
    ) -> str:
        return await self._task_agent.handle_command(db, user_id, intent, message)

    async def _route_calendar(
        self, db: AsyncSession, user_id: uuid.UUID, intent: str, message: str
    ) -> str:
        return await self._scheduling_agent.handle_command(db, user_id, intent, message)

    async def _route_knowledge(
        self, db: AsyncSession, user_id: uuid.UUID, intent: str, message: str
    ) -> str:
        agent = KnowledgeAgent(ollama=self._ollama)
        return await agent.handle_command(db, user_id, intent, message)

    async def _route_research(self, message: str) -> str:
        return (
            "🔍 *Research agent* is coming in Phase 5! I'll be able to search the web, "
            "synthesize information from multiple sources, and generate executive reports."
        )

    async def _handle_memory(
        self, db: AsyncSession, user_id: uuid.UUID, intent: str, message: str
    ) -> str:
        if intent == "memory_store":
            from app.memory.long_term import store_memory

            await store_memory(
                db,
                user_id=user_id,
                memory_type="fact",
                content=message,
                source="whatsapp",
            )
            return "Got it! I've saved that to my memory. 🧠"
        else:
            from app.memory.long_term import search_memories

            memories = await search_memories(db, user_id=user_id, query=message, limit=5)
            if not memories:
                return "I don't have any relevant memories about that yet."
            lines = [f"• {m.summary or m.content[:100]}" for m in memories[:5]]
            return "Here's what I remember:\n" + "\n".join(lines)
