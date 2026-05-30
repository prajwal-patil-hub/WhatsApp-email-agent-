# Project Progress — Personal AI Chief of Staff
> **Last Updated:** 2026-05-30
> **Overall Completion:** 14% (Phase 1 of 7 complete)
> **Active Branch:** `claude/personal-ai-chief-of-staff-xAqWZ`
> **Open PR:** https://github.com/prajwal-patil-hub/WhatsApp-email-agent-/pull/1

---

## Summary Scorecard

| Phase | Name | Status | Files | Lines | Tests |
|---|---|---|---|---|---|
| 1 | Core WhatsApp Assistant | ✅ COMPLETE | 90 | 6,626 | 5 test files |
| 2 | Email Integration | ⬜ NOT STARTED | — | — | — |
| 3 | Task Management | ⬜ NOT STARTED | — | — | — |
| 4 | Knowledge Base + Calendar | ⬜ NOT STARTED | — | — | — |
| 5 | Research Agent | ⬜ NOT STARTED | — | — | — |
| 6 | Admin Dashboard | ⬜ NOT STARTED | — | — | — |
| 7 | Advanced Automations | ⬜ NOT STARTED | — | — | — |
| **TOTAL** | | | **90** | **6,626** | |

---

## ✅ PHASE 1 — Core WhatsApp Assistant
**Completed:** 2026-05-30
**Commit:** `f4c95b5` (rebased onto main)
**All 52 deliverables complete.**

### Infrastructure
- [x] `docker-compose.yml` — 7 services (PostgreSQL 16, Redis 7, Qdrant, Ollama, FastAPI, n8n, React), all with healthchecks and named volumes
- [x] `.env.example` — 30+ variables with generation instructions and comments
- [x] `Makefile` — 12 commands: up, down, restart, logs, migrate, migrate-create, test, lint, typecheck, pull-model, backup, clean
- [x] `.gitignore` — Python, Node, Docker volumes, secrets, test artifacts
- [x] `backend/Dockerfile` — multi-stage: base → development → production (non-root user)
- [x] `frontend/Dockerfile` — multi-stage: node build → nginx serve
- [x] `frontend/nginx.conf` — static file serving + API proxy

### Architecture Documentation
- [x] `ARCHITECTURE.md` — 1,200+ line comprehensive document including:
  - ASCII system overview diagram
  - Component descriptions (all 7 services)
  - Data flow diagrams (text message + voice note + long-term memory)
  - Full database ERD (8 tables with all columns and indexes)
  - API endpoint catalog
  - n8n workflow descriptions
  - Security design (HMAC, JWT, RBAC, audit)
  - Complete folder structure (all 7 phases)
  - Implementation roadmap (phases 1–7 with milestones)
  - Technology decisions with trade-offs
  - Operational runbook

### Backend Core (`backend/app/core/`)
- [x] `config.py` — Pydantic Settings v2, `@lru_cache`, `validate_required()` startup check
- [x] `database.py` — async SQLAlchemy 2.0 engine, session factory, `create_tables()`, `dispose_engine()`
- [x] `security.py` — `create_access_token()`, `decode_token()`, `verify_whatsapp_signature()` (HMAC with positional args fix)
- [x] `logging.py` — structlog setup (JSON prod / console dev), suppress noisy loggers

### Database Models (`backend/app/models/db/`)
- [x] `base.py` — SQLAlchemy `DeclarativeBase`
- [x] `user.py` — `id` (UUID PK), `phone_number` (unique), `name`, `email`, `role`, `is_active`, `preferences` (JSONB), `timezone`
- [x] `conversation.py` — `user_id` (FK), `channel`, `status`, `title`, `metadata` (JSONB)
- [x] `message.py` — `conversation_id` (FK), `role`, `content`, `message_type`, `wa_message_id` (unique dedup), `transcription`, `tokens_used`, `model_used`
- [x] `session.py` — `token_jti` (unique), `expires_at`, `revoked` — JWT revocation table
- [x] `memory.py` — `memory_type`, `content`, `embedding_id` (Qdrant point ID), `importance`, `access_count`, `last_accessed`, `expires_at`
- [x] `task.py` — `title`, `priority`, `status`, `due_date`, `project`, `tags` (ARRAY), `recurrence`, `source_message_id` (FK)
- [x] `knowledge.py` — `source_type`, `content_hash` (SHA256 dedup), `chunk_count`, `status` — Phase 4 schema
- [x] `audit.py` — `action`, `resource_type`, `resource_id`, `status`, `details` (JSONB), `duration_ms` — append-only

### Pydantic Schemas (`backend/app/models/schemas/`)
- [x] `whatsapp.py` — `WAWebhookPayload`, `WAInboundMessage`, `WAAudioContent`, `WAOutboundMessage`, `ProcessedWhatsAppMessage`
- [x] `message.py` — `MessageResponse`, `ConversationResponse`, `PaginatedMessages`, `PaginatedConversations`
- [x] `memory.py` — `MemoryCreate`, `MemoryUpdate`, `MemoryResponse`, `PaginatedMemories`
- [x] `auth.py` — `TokenRequest`, `TokenResponse`, `TokenPayload`

### Database Migrations (`backend/migrations/`)
- [x] `env.py` — async Alembic env, DATABASE_URL from environment
- [x] `script.py.mako` — migration template
- [x] `versions/001_initial_schema.py` — creates all 8 tables with indexes, pgcrypto extension

### Services (`backend/app/services/`)
- [x] `ollama.py` — `OllamaService`: async `chat()`, `embed()`, `is_available()`, `list_models()`; tenacity retry (3 attempts, exponential backoff 2–10s); singleton `get_ollama_service()`
- [x] `whisper.py` — `transcribe_audio()` (bytes), `transcribe_file()` (path), `_mime_to_suffix()`, `warmup_whisper()`; lazy model loading; faster-whisper with VAD filter
- [x] `whatsapp.py` — `WhatsAppService`: `send_text()`, `send_typing_indicator()`, `get_media_url()`, `download_media()`; singleton pattern
- [x] `edge_tts.py` — `text_to_speech()` stub with interface; `AVAILABLE_VOICES` list
- [x] `audit.py` — `log_action()` async function; writes AuditLog row + structlog event

### Memory System (`backend/app/memory/`)
- [x] `short_term.py` — Redis-based; `get_context()`, `add_message()`, `clear_context()`, `set_context()`, `ping()`; asyncio.Lock singleton; TTL 24h; sliding window trim
- [x] `working.py` — PostgreSQL-based; `get_working_context()`, `upsert_goal()`, `touch_memories()`; 30-day retention
- [x] `long_term.py` — `store_memory()`, `search_memories()`, `delete_memory()`; Qdrant hooks `_store_embedding()` / `_delete_embedding()` (graceful degradation if Qdrant unavailable)

### Agents (`backend/app/agents/`)
- [x] `coordinator.py` — **FULLY IMPLEMENTED Phase 1**:
  - `ExecutiveCoordinator.process()` — main entry point
  - `_classify_intent()` — calls Ollama (mistral) with 15-intent classifier prompt, temperature=0
  - `_chat_response()` — loads Redis context, builds prompt, calls Ollama (qwen3), saves context
  - `_route_email()`, `_route_task()`, `_route_calendar()`, `_route_knowledge()`, `_route_research()` — stub responses with phase ETA
  - `_handle_memory()` — real implementation: stores/searches long-term memories
  - `CoordinatorResponse` dataclass with intent, model_used, tokens_used, processing_ms, routed_to
- [x] `email_agent.py` — STUB. `EmailSummary`, `DraftedEmail` dataclasses. 3 methods raise `NotImplementedError("Phase 2")`
- [x] `task_agent.py` — STUB. `TaskResult` dataclass. 3 methods raise `NotImplementedError("Phase 3")`
- [x] `research_agent.py` — STUB. `ResearchReport` dataclass. 2 methods raise `NotImplementedError("Phase 5")`
- [x] `knowledge_agent.py` — STUB. `KnowledgeResult` dataclass. 3 methods raise `NotImplementedError("Phase 4")`
- [x] `scheduling_agent.py` — STUB. `CalendarEvent` dataclass. 3 methods raise `NotImplementedError("Phase 4")`

### API Layer (`backend/app/api/`)
- [x] `deps.py` — `get_current_user()` (JWT verify + JTI revocation check), `require_admin()`, `get_client_ip()`; type aliases `CurrentUser`, `AdminUser`, `Database`, `OllamaClient`, `WhatsAppClient`
- [x] `router.py` — aggregates all routes under `/api/v1`
- [x] `routes/health.py` — `GET /health` (liveness), `GET /health/ready` (checks PostgreSQL + Redis + Ollama)
- [x] `routes/auth.py` — `POST /auth/token` (admin bootstrap, creates User if new, issues JWT, creates Session row), `POST /auth/revoke`
- [x] `routes/whatsapp.py` — `GET /webhook` (Meta challenge), `POST /webhook` (HMAC verify, dedup, background task), `POST /voice` (upload+transcribe); background tasks use own DB session (critical fix)
- [x] `routes/messages.py` — `GET /messages/conversations` (paginated), `GET /messages/conversations/{id}` (paginated messages)
- [x] `routes/memory.py` — `GET /memory`, `POST /memory`, `PUT /memory/{id}`, `DELETE /memory/{id}`
- [x] `main.py` — app factory, lifespan (validate_required → create_tables → warmup_whisper in executor), CORS, global exception handler

### n8n Workflows (`n8n/workflows/`)
- [x] `whatsapp_ingestion.json` — nodes: Webhook Trigger → Extract Payload → Respond OK + Verify & Parse Message → Route by Type → Forward Text/Voice to Backend → Error Handler
- [x] `morning_briefing.json` — nodes: Schedule Trigger (7am Mon-Fri) → Get Pending Tasks + Get Active Goals → Build Briefing Text → Send via WhatsApp → Log Sent

### Frontend (`frontend/`)
- [x] `package.json` — React 18, TanStack Query v5, Axios, react-router-dom v6, lucide-react, Tailwind 3
- [x] `vite.config.ts` — Vite 6, React plugin, proxy to backend
- [x] `tailwind.config.js`, `tsconfig.json`, `tsconfig.node.json`
- [x] `src/main.tsx` — React root mount
- [x] `src/App.tsx` — QueryClientProvider, BrowserRouter, 5 routes
- [x] `src/components/Layout.tsx` — dark sidebar nav with NavLink active states, phase status indicator
- [x] `src/pages/Dashboard.tsx` — health query (30s refetch), stats grid, PhaseRoadmap component, QuickActions
- [x] `src/pages/Conversations.tsx` — skeleton
- [x] `src/pages/Tasks.tsx` — skeleton with Phase 3 notice
- [x] `src/pages/Memory.tsx` — skeleton
- [x] `src/pages/Settings.tsx` — skeleton

### Tests (`backend/tests/`)
- [x] `conftest.py` — test engine (SQLite), db_session fixture, mock_settings, mock_ollama, mock_redis, mock_whatsapp, payload fixtures
- [x] `fixtures/whatsapp_messages.json` — text_message, voice_message, status_update payloads
- [x] `unit/test_coordinator.py` — 12 tests: intent classification (valid/invalid/error), routing stubs (5), chat with history + context injection
- [x] `unit/test_memory.py` — 8 tests: short-term (add/get/trim/clear/ping/fail), long-term (store/search-by-type/delete/not-found)
- [x] `unit/test_whisper.py` — 10 tests: mime suffix, transcription, multi-segment join, empty audio, warmup failure; security (HMAC valid/invalid/missing, JWT create/decode/invalid)
- [x] `integration/test_health.py` — health 200 + schema contract
- [x] `integration/test_whatsapp_webhook.py` — 8 tests: verification valid/invalid, text/voice/status payload parsing, HMAC valid/tampered/missing, dedup tracking/eviction

### Documentation (`docs/`)
- [x] `docs/phase1-setup.md` — 10-step setup guide with troubleshooting

### Quality / Bugs Fixed

6 bugs caught and fixed by adversarial 5-angle code review:

| # | Severity | File | Bug | Fix Applied |
|---|---|---|---|---|
| 1 | **Critical** | `core/security.py` | `hmac.new(key=...)` keyword args → `TypeError` crashes all webhook POSTs | Changed to positional args |
| 2 | **Critical** | `api/routes/whatsapp.py` | Request-scoped `AsyncSession` passed to `BackgroundTasks` → session closed before task runs, all DB ops fail | Background task uses `get_session_factory()()` to create own session |
| 3 | **High** | `core/security.py` | Malformed HMAC header raises `TypeError` in `compare_digest` → 500 instead of 403 | Wrapped in `try/except (TypeError, ValueError): return False` |
| 4 | **Medium** | `main.py` | `warmup_whisper()` sync blocking in async lifespan blocks event loop during startup | `await asyncio.get_event_loop().run_in_executor(None, warmup_whisper)` |
| 5 | **Medium** | `api/routes/health.py` | Generator `get_db()` not cleaned up in exception path → PostgreSQL connection leak | `async with get_session_factory()()` context manager |
| 6 | **Medium** | `memory/short_term.py` | Lazy Redis singleton without lock → concurrent startup creates duplicate connection pools | `asyncio.Lock()` with double-checked locking pattern |

---

## ⬜ PHASE 2 — Email Integration
**Status:** NOT STARTED
**Estimated Effort:** 2 weeks
**Prerequisites:** Phase 1 running end-to-end successfully

### Checklist
#### Gmail Integration
- [ ] Add Gmail pip packages: `google-auth-oauthlib`, `google-api-python-client`
- [ ] Create `backend/app/services/gmail.py` — OAuth2 flow, token storage, inbox read, send
- [ ] Create `backend/app/api/routes/email.py` — OAuth callback, email list, draft, send
- [ ] Add email OAuth credentials to `users` table (migration `002_email_oauth.py`)
- [ ] Implement `EmailAgent.get_unread_summary()` — calls Gmail API, summarizes with LLM
- [ ] Implement `EmailAgent.draft_reply()` — fetches thread, generates reply with context
- [ ] Implement `EmailAgent.send_email()` — sends via Gmail API
- [ ] Wire coordinator: `email_read/draft/send` → `EmailAgent` (currently returns stub)
- [ ] WhatsApp command: "Summarize today's emails" → top 10 unread with AI summary
- [ ] WhatsApp command: "Draft reply to [name/subject]" → AI-drafted email
- [ ] WhatsApp command: "Send the draft" → confirmation + send

#### Outlook Integration
- [ ] Add `msal` package for Microsoft auth
- [ ] Create `backend/app/services/outlook.py` — OAuth2, inbox, send
- [ ] Extend `EmailAgent` to support both Gmail and Outlook (provider routing)

#### Automation
- [ ] Create `n8n/workflows/email_monitor.json` — poll Gmail every 5 min, push urgent to WhatsApp
- [ ] Priority email detection (invoice, urgent, from VIP contacts)
- [ ] Follow-up reminder: flag emails needing reply after 24h

#### Tests
- [ ] `tests/unit/test_email_agent.py`
- [ ] `tests/integration/test_email_routes.py`

---

## ⬜ PHASE 3 — Task Management
**Status:** NOT STARTED
**Estimated Effort:** 2 weeks
**Prerequisites:** Phase 1

### Checklist
- [ ] Implement `TaskAgent.create_from_message()` — NL parsing → task fields extraction
- [ ] Implement `TaskAgent.list_tasks()` — filter by status/priority/project
- [ ] Implement `TaskAgent.complete_task()` — mark done, trigger recurrence if set
- [ ] Natural language priority inference ("ASAP" → urgent, "sometime" → low)
- [ ] Natural language due date parsing ("next Friday", "in 3 days")
- [ ] Recurring task engine — cron scheduler using APScheduler or Celery Beat
- [ ] Due date reminder system — check overdue tasks every hour, WhatsApp nudge
- [ ] Wire coordinator: `task_create/list/update` → `TaskAgent`
- [ ] WhatsApp commands: "Create task", "Show my tasks", "Complete task X"
- [ ] Project grouping: "Add to project: AI Learning"
- [ ] Proactive overdue nudge: daily 9am check for overdue tasks
- [ ] Create `n8n/workflows/task_reminders.json`
- [ ] Activate Edge TTS: voice reply option for task confirmations
- [ ] Tests: `tests/unit/test_task_agent.py`, `tests/integration/test_task_routes.py`

---

## ⬜ PHASE 4 — Knowledge Base + Calendar
**Status:** NOT STARTED
**Estimated Effort:** 2 weeks
**Prerequisites:** Phase 1 (Qdrant already in Docker Compose)

### Checklist
#### Knowledge Base (RAG Pipeline)
- [ ] Add `pypdf`, `python-docx`, `langchain-text-splitters` or custom chunker
- [ ] Implement `KnowledgeAgent.ingest_document()` — PDF/DOCX/TXT/MD → chunks → embeddings → Qdrant
- [ ] Implement `KnowledgeAgent.search()` — query → embed → Qdrant search → top-k chunks
- [ ] Implement `KnowledgeAgent.answer()` — RAG: search + LLM grounded answer
- [ ] Create Qdrant collection `knowledge` on startup
- [ ] Activate Qdrant for long-term memory (`long_term.py` `_store_embedding()` already written)
- [ ] Create Qdrant collection `memories` on startup
- [ ] WhatsApp: send PDF → transcribe/ingest → "Document indexed ✅"
- [ ] WhatsApp: "Find my Deloitte notes" → semantic search + summary
- [ ] Add `POST /api/v1/knowledge/ingest` endpoint
- [ ] Add `GET /api/v1/knowledge/search` endpoint
- [ ] Web page ingestion: `services/web_scraper.py` using `httpx` + `BeautifulSoup`
- [ ] Wire coordinator: `knowledge_search/ingest` → `KnowledgeAgent`

#### Calendar
- [ ] Add Google Calendar OAuth2 (`google-api-python-client`)
- [ ] Implement `SchedulingAgent.get_agenda()` — list events for a day
- [ ] Implement `SchedulingAgent.schedule_meeting()` — NL → create event
- [ ] Implement `SchedulingAgent.find_slot()` — find free slot for attendees
- [ ] Conflict detection before scheduling
- [ ] Meeting prep brief: "Your 3pm meeting with X — here's context..."
- [ ] Wire coordinator: `calendar_schedule/query` → `SchedulingAgent`
- [ ] Tests for both knowledge and scheduling agents

---

## ⬜ PHASE 5 — Research Agent
**Status:** NOT STARTED
**Estimated Effort:** 2 weeks
**Prerequisites:** Phase 4 (knowledge base for saving reports)

### Checklist
- [ ] Add `brave-search` or set up SearXNG container
- [ ] Implement `ResearchAgent.research()` — query → search → fetch pages → synthesize → report
- [ ] Implement `ResearchAgent.compare()` — side-by-side comparison of topics
- [ ] Executive summary generation with LLM (deepseek-r1 for quality)
- [ ] Citation tracking — save sources with each report
- [ ] Report export: Markdown + PDF (WeasyPrint or reportlab)
- [ ] Auto-save research to knowledge base
- [ ] Wire coordinator: `research` → `ResearchAgent`
- [ ] WhatsApp: "Research top AI agent frameworks" → structured report
- [ ] WhatsApp: "Compare Claude vs GPT-4o" → comparison table
- [ ] `POST /api/v1/research` endpoint
- [ ] `GET /api/v1/research/reports` endpoint
- [ ] Tests: `tests/unit/test_research_agent.py`

---

## ⬜ PHASE 6 — Admin Dashboard
**Status:** NOT STARTED
**Estimated Effort:** 2 weeks
**Prerequisites:** Phases 1–3 (enough data to display)

### Checklist
#### Pages to Build (frontend/src/pages/)
- [ ] `Conversations.tsx` — full thread view with message bubbles, search, filter by channel
- [ ] `Tasks.tsx` — Kanban board (pending/in-progress/completed), drag-and-drop
- [ ] `Memory.tsx` — list with type filter, search, inline edit/delete
- [ ] `Knowledge.tsx` — file upload UI, document list, search interface
- [ ] `Research.tsx` — report list, full report viewer with citations
- [ ] `AuditLog.tsx` — paginated action log with filters
- [ ] `SystemHealth.tsx` — service status cards, latency charts, token usage

#### New Components
- [ ] `MessageBubble.tsx` — WhatsApp-style bubble
- [ ] `KanbanBoard.tsx` — drag-and-drop task board
- [ ] `FileUploader.tsx` — drag-and-drop document ingest
- [ ] `HealthCard.tsx` — service status with live polling
- [ ] `MetricsChart.tsx` — messages/day, tasks/week charts

#### API Additions
- [ ] `GET /api/v1/admin/audit` — paginated audit log with filters
- [ ] `GET /api/v1/admin/users` — user management
- [ ] `GET /api/v1/admin/system/health` — all service health in one call
- [ ] `GET /api/v1/analytics/messages` — messages per day/week
- [ ] `GET /api/v1/analytics/tasks` — task completion metrics

#### Infrastructure
- [ ] Dashboard JWT refresh token flow (extend `auth.py`)
- [ ] WebSocket for live conversation updates (or SSE)
- [ ] Responsive mobile CSS (Tailwind breakpoints)

---

## ⬜ PHASE 7 — Advanced Automations
**Status:** NOT STARTED
**Estimated Effort:** 4 weeks
**Prerequisites:** All previous phases

### Checklist
#### Smart Automations
- [ ] Invoice processor: detect invoice email → extract amount/due date/vendor → create task → notify
- [ ] Meeting invite processor: detect calendar invite → summarize → check conflicts → suggest accept/decline
- [ ] Email auto-routing: classify all incoming email → tag/label/create tasks automatically
- [ ] Proactive context injection: "Your 2pm meeting with Prajwal is in 30 minutes. Here's prep..."
- [ ] Daily executive briefing: 7am → calendar + emails + tasks + project updates (extend n8n workflow)

#### Voice
- [ ] Activate `edge_tts.py` for voice replies
- [ ] WhatsApp voice note reply option (send audio response)
- [ ] Language detection → match TTS voice language

#### Additional Channels
- [ ] Telegram bot integration
- [ ] Slack app integration  
- [ ] Microsoft Teams webhook

#### Infrastructure
- [ ] Multi-model routing: mistral (fast <1s), qwen3 (general), deepseek-r1 (research/analysis)
- [ ] Replace ngrok with Cloudflare Tunnel (persistent public URL)
- [ ] Add Celery + Redis as task queue (replace BackgroundTasks for heavy workloads)
- [ ] Add rate limiting (fastapi-limiter + Redis)
- [ ] Column-level encryption for messages.content and memories.content (pgcrypto)
- [ ] Horizontal scaling prep: stateless backend, shared Redis/PG

---

## Changelog

| Date | Version | Change |
|---|---|---|
| 2026-05-30 | v1.0.0 | Phase 1 complete. 90 files, 6,626 lines. PR #1 opened. 6 bugs fixed. CONTEXT.md + PROGRESS.md created. |

---

## Known Issues / Tech Debt

| ID | Severity | Description | File | Fix In |
|---|---|---|---|---|
| TD-1 | Low | In-memory `_processed_ids` set in `whatsapp.py` for dedup is process-local — won't work with multiple backend workers | `api/routes/whatsapp.py` | Phase 7 (move to Redis sorted set with TTL) |
| TD-2 | Low | `conftest.py` uses SQLite for tests but production uses PostgreSQL — JSONB, UUID, ARRAY types may behave differently | `tests/conftest.py` | Phase 3 (add PostgreSQL test container via testcontainers) |
| TD-3 | Low | Frontend pages (Conversations, Tasks, Memory, Settings) are skeletons with no real data fetching | `frontend/src/pages/` | Phase 6 |
| TD-4 | Low | No rate limiting on webhook endpoint — potential for abuse if token is leaked | `api/routes/whatsapp.py` | Phase 7 |
| TD-5 | Low | `REQUIRED_VARS` in `config.py` is a plain list, not validated by Pydantic — could go stale | `core/config.py` | Phase 3 (use `__fields__` introspection) |

---

## File Inventory (Phase 1 Complete)

```
90 files total
├── Root (6): ARCHITECTURE.md, CONTEXT.md, PROGRESS.md, Makefile, docker-compose.yml, .env.example, .gitignore
├── backend/ (59 files)
│   ├── Dockerfile, alembic.ini, requirements.txt
│   ├── app/core/ (4): config, database, logging, security
│   ├── app/agents/ (6): coordinator, email, task, research, knowledge, scheduling
│   ├── app/api/ (7): deps, router, routes/auth, health, messages, memory, whatsapp
│   ├── app/memory/ (3): short_term, working, long_term
│   ├── app/models/db/ (9): base + 8 ORM models
│   ├── app/models/schemas/ (4): auth, memory, message, whatsapp
│   ├── app/services/ (5): audit, edge_tts, ollama, whatsapp, whisper
│   ├── app/main.py
│   ├── migrations/ (3): env.py, script.py.mako, 001_initial_schema.py
│   └── tests/ (10): conftest, fixtures/json, 3 unit, 2 integration, __init__ files
├── n8n/workflows/ (2): whatsapp_ingestion.json, morning_briefing.json
├── frontend/ (18 files)
│   ├── Dockerfile, nginx.conf, index.html, package.json, tailwind.config.js, tsconfig.json, tsconfig.node.json, vite.config.ts
│   ├── src/: main.tsx, index.css, App.tsx
│   ├── src/components/: Layout.tsx
│   └── src/pages/: Dashboard, Conversations, Tasks, Memory, Settings
└── docs/ (1): phase1-setup.md
```

---

*This file is updated at the end of every session. Do not manually edit — update via Claude Code sessions only.*
