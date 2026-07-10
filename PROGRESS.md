# Project Progress — Personal AI Chief of Staff
> **Last Updated:** 2026-05-30
> **Overall Completion:** 100% — ALL 7 PHASES COMPLETE 🎉
> **Last Updated:** 2026-07-10
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

## ✅ PHASE 2 — Email Integration
**Status:** COMPLETE (2026-07-06)
**Delivered:** Gmail + Outlook OAuth2, EmailAgent (read/draft/send), 6 API routes, encrypted token storage, email monitor workflow, 24 tests

### Checklist
#### Gmail Integration
- [x] Added pip packages: `google-auth-oauthlib`, `google-api-python-client`, `msal`
- [x] `backend/app/services/email_provider.py` — abstract EmailProvider interface + EmailMessage/EmailThread dataclasses
- [x] `backend/app/services/gmail.py` — GmailProvider: OAuth2 credentials + auto-refresh, unread list, thread fetch, MIME send, mark-as-read (sync SDK wrapped in asyncio.to_thread)
- [x] `backend/app/api/routes/email.py` — /auth/gmail (+callback), /auth/outlook (+callback), /status, /inbox, /send, /disconnect/{provider}
- [x] Migration `002_email_oauth.py` — dedicated `email_credentials` table (not on users: supports multiple providers per user), unique (user_id, provider)
- [x] Tokens encrypted at rest with Fernet (key derived SHA256(SECRET_KEY)); transparent refresh + re-persist via `_sync_tokens`
- [x] `EmailAgent.handle_command()` — read (LLM inbox summary with urgency flags), draft (thread-aware LLM reply), send (LLM command parser extracts recipient/subject/body, validates address)
- [x] Wired coordinator: `email_read/draft/send` → real EmailAgent; system prompt updated
- [x] WhatsApp commands work end-to-end: "check my emails", "draft reply to #2", "send email to x@y.com ..."

#### Outlook Integration
- [x] `msal` package for Microsoft auth
- [x] `backend/app/services/outlook.py` — OutlookProvider: MSAL refresh-token flow, Graph API inbox/thread/send/mark-read via httpx, HTML→text stripping
- [x] EmailAgent routes by `email_credentials.provider` — Gmail and Outlook both supported

#### Automation
- [x] `n8n/workflows/email_monitor.json` — every 5 min: fetch inbox summary → skip if 0 unread → WhatsApp notification → audit log
- [ ] Priority email detection from VIP contacts (deferred → Phase 7 automations)
- [ ] Follow-up reminder after 24h (deferred → Phase 7 automations)

#### Security
- [x] OAuth CSRF protection — signed JWT state tokens (`purpose=oauth_state`, provider-bound)
- [x] All email actions audit-logged (email.read / email.draft / email.send / email.*_connected / email.*_disconnected)

#### Tests (24 new, 70/70 total passing)
- [x] `tests/unit/test_email_agent.py` — 11 tests: encryption roundtrip, no-credentials message, read empty/full inbox, send validation + success, draft, token sync, provider error handling
- [x] `tests/integration/test_email_routes.py` — 13 tests: auth required, status, OAuth not-configured 503, auth URL generation, disconnect, inbox 412/200, send 412/200

### Bugs Fixed During Phase 2
| # | Severity | Location | Bug | Fix |
|---|---|---|---|---|
| 7 | **High** | `api/routes/whatsapp.py` | `_track_processed` rebound module global `_processed_ids` to a new set on eviction — other references kept the stale, unbounded set | Mutate in place: `clear()` + `update()` |
| 8 | **Medium** | `models/db/*.py` | Postgres-only `JSONB`/`ARRAY` column types in ORM broke SQLite test runs (and any non-PG deployment) | Cross-dialect `JSON` in ORM; migrations keep JSONB on Postgres |
| 9 | **Medium** | `tests/conftest.py` | Session-scoped DB engine leaked committed rows across tests → unique-constraint and multiple-rows failures | Function-scoped in-memory SQLite with StaticPool; autouse env fixture so `get_settings()` always valid |
| 10 | **Low** | `tests/unit/test_memory.py` | Patched `app.core.config.get_settings` instead of the imported reference in `short_term` — mock never applied | Patch `app.memory.short_term.get_settings` |

---

## ✅ PHASE 3 — Task Management
**Status:** COMPLETE (2026-07-09)
**Delivered:** TaskAgent (NL create/list/complete/update/delete), REST CRUD API, recurrence engine, hourly reminder workflow, 24 tests

### Checklist
- [x] `TaskAgent.handle_command()` — one LLM parse (action/title/priority/due/project/recurrence/task_ref) → dispatch
- [x] List with status filter, priority emoji, overdue flags, numbered for follow-up commands
- [x] Complete by list number or title keyword; recurring tasks spawn next occurrence (daily/weekly/monthly, catch-up loop if far past due)
- [x] NL priority inference in parser prompt ("ASAP" → urgent, "sometime" → low, default medium; invalid values clamp to medium)
- [x] NL due-date parsing — LLM resolves "tomorrow 5pm"/"next Friday" to ISO given current UTC datetime; defensive ISO parse fallback to None
- [x] Recurrence engine — no extra scheduler dependency: next occurrence created on completion; n8n owns time-based nudges
- [x] Reminder system — GET /tasks/overdue?mark_reminded=true (stamps reminder_sent_at so each task nudges once) + hourly `task_reminders.json` n8n workflow
- [x] Wire coordinator: task_create/task_list/task_update → TaskAgent
- [x] WhatsApp commands work: "add task: call dentist tomorrow 3pm", "show my tasks", "complete task 2", "make the slides task urgent", "delete task 1"
- [x] Project grouping via parser (project field) + API filter ?project=
- [x] REST API: GET/POST /tasks, GET/PATCH/DELETE /tasks/{id}, POST /tasks/{id}/complete — morning_briefing.json GET /tasks now live
- [x] Tests: 13 unit (test_task_agent.py) + 11 integration (test_task_routes.py); full suite 94/94
- [ ] Proactive overdue nudge: daily 9am check for overdue tasks
- [ ] Create `n8n/workflows/task_reminders.json`
- [ ] Activate Edge TTS: voice reply option for task confirmations
- [ ] Tests: `tests/unit/test_task_agent.py`, `tests/integration/test_task_routes.py`

---

## ✅ PHASE 4 — Knowledge Base + Calendar
**Status:** COMPLETE (2026-07-09)
**Delivered:** Qdrant RAG pipeline, KnowledgeAgent with citations, Google Calendar + SchedulingAgent, semantic long-term memory, 32 tests

### Checklist
#### Knowledge Base (RAG Pipeline)
- [x] Custom paragraph-aware chunker in `services/documents.py` (1200 chars, 200 overlap; pypdf/python-docx already in requirements — no new deps)
- [x] `KnowledgeAgent.ingest_document()` / `ingest_note()` — PDF/DOCX/TXT/MD → chunks → nomic-embed-text embeddings → Qdrant; SHA-256 content_hash dedup; per-chunk failure tolerance (status ready/failed)
- [x] `KnowledgeAgent.search()` — embed query → user-filtered Qdrant search → top-k chunks with scores
- [x] `KnowledgeAgent.answer()` — RAG with inline [n] citations + source list; honest "not in knowledge base" fallback
- [x] Qdrant collections (`knowledge`, `memories`, 768-dim cosine) bootstrapped in app lifespan, non-fatal if Qdrant down
- [x] Long-term memory activated: store_memory embeds by default; search_memories semantic-first (relevance-ordered) with PG fallback
- [x] WhatsApp: "remember this: ..." → ingested as note; questions answered from KB
- [x] API: GET /knowledge, POST /knowledge/upload (20MB cap, type validation), POST /knowledge/ask, DELETE /knowledge/{id}
- [ ] Web page ingestion (deferred → Phase 5 research agent shares the fetch pipeline)
- [x] Wire coordinator: knowledge_search/ingest → KnowledgeAgent

#### Calendar
- [x] Google Calendar OAuth2 — reuses Gmail client credentials + email_credentials table (provider="gcal"), Fernet-encrypted tokens, transparent refresh
- [x] `SchedulingAgent` agenda queries — "what's on today/next Monday" → day event list
- [x] NL scheduling — LLM parses title/start/duration/attendees/location against current datetime → create event with invites (sendUpdates=all)
- [x] Conflict detection — overlapping events flagged in the confirmation message
- [ ] find_slot / meeting prep briefs (deferred → Phase 7 automations)
- [x] Wire coordinator: calendar_schedule/query → SchedulingAgent
- [x] Tests: 15 unit (knowledge+documents) + 7 unit (scheduling) + 11 integration (routes); full suite 126/126

---

## ✅ PHASE 5 — Research Agent
**Status:** COMPLETE (2026-07-10)
**Delivered:** Web search (Brave/SearXNG), 4-source concurrent fetch, deepseek-r1 synthesis with citations, KB auto-save

### Checklist
- [x] `services/web_search.py` — Brave Search API (BRAVE_SEARCH_API_KEY) or SearXNG (SEARXNG_URL); no new pip deps (httpx + regex extraction)
- [x] `ResearchAgent.research()` — search → concurrent page fetch (unreadable pages fall back to snippets) → synthesize → report
- [x] Comparisons handled by the synthesis prompt ("structure findings as a comparison" when asked)
- [x] Executive summary via OLLAMA_REASONING_MODEL (deepseek-r1); <think> reasoning blocks stripped from output
- [x] Citation tracking — inline [n] + full source URL list appended
- [ ] PDF export (deferred — reports are WhatsApp-native text + searchable in KB)
- [x] Auto-save to knowledge base (source_type="research") — future questions RAG over past reports
- [x] Wire coordinator: research → ResearchAgent
- [x] WhatsApp: "Research top AI agent frameworks" → structured cited report
- [x] POST /api/v1/research + GET /api/v1/research/reports
- [x] Tests: tests/unit/test_research_agent.py (8) + integration (3)

---

## ✅ PHASE 6 — Admin Dashboard
**Status:** COMPLETE (2026-07-10)
**Delivered:** 5 admin/analytics API endpoints + 8-page React dashboard with JWT auth; build + typecheck green

### Checklist
#### Pages to Build (frontend/src/pages/)
- [x] `Conversations.tsx` — thread list + WhatsApp-style message bubbles (voice markers, timestamps)
- [x] `Tasks.tsx` — 3-column board (pending/in-progress/completed) with create/complete/cancel (drag-and-drop deferred)
- [x] `Memory.tsx` — list with type filter chips, importance + dates
- [x] `Knowledge.tsx` — upload button (PDF/DOCX/TXT/MD), document list with chunk counts, ask-your-KB panel
- [x] `Research.tsx` — run research from the dashboard, view cited report, past reports list
- [x] `AuditLog.tsx` — live-refreshing table with action-prefix filter chips
- [x] Service health folded into Dashboard.tsx — live PG/Redis/Qdrant/Ollama status + task analytics tiles

#### New Components
- [x] Message bubbles inline in Conversations.tsx
- [x] Column board inline in Tasks.tsx
- [x] File upload inline in Knowledge.tsx
- [x] ServiceHealth component in Dashboard.tsx (30s polling)
- [x] Analytics tiles in Dashboard.tsx (charts deferred)

#### API Additions
- [x] GET /api/v1/admin/audit — paginated, action-prefix filter, admin-gated
- [x] GET /api/v1/admin/users
- [x] GET /api/v1/admin/system/health — PG/Redis/Qdrant/Ollama in one call
- [x] GET /api/v1/admin/analytics/messages — per-day counts
- [x] GET /api/v1/admin/analytics/tasks — status breakdown + completed-last-7-days

#### Infrastructure
- [x] Dashboard JWT auth — Settings page login (phone + ADMIN_SECRET), axios interceptor, 401 auto-logout
- [ ] WebSocket live updates (deferred — 30s polling via react-query refetchInterval)
- [x] Responsive grids (lg: breakpoints); FIXED missing postcss.config.js that silently disabled Tailwind entirely

---

## ✅ PHASE 7 — Advanced Automations
**Status:** COMPLETE (2026-07-10)
**Delivered:** Live briefing service, voice TTS replies, meeting-prep + weekly-review + overdue-nudge automations

### Checklist
#### Smart Automations
- [ ] Invoice processor (future enhancement — email monitor workflow is the hook point)
- [ ] Meeting invite processor (future enhancement)
- [ ] Email auto-routing (future enhancement)
- [x] Meeting prep — GET /calendar/upcoming + meeting_prep.json (15-min poll, per-event dedup via n8n staticData)
- [x] Daily executive briefing — services/briefing.py aggregates tasks/calendar/goals with per-section fault isolation; GET /api/v1/briefing; morning_briefing.json now one API call; WhatsApp 'briefing' intent live

#### Voice
- [x] Edge TTS activated — voice notes get spoken replies
- [x] WhatsAppService.send_audio — media upload + audio message
- [ ] TTS language detection (future enhancement — en-US default)

#### Additional Channels
- [ ] Telegram/Slack/Teams channels (out of scope — WhatsApp-first by design)
- [ ] Slack app integration  
- [ ] Microsoft Teams webhook

#### Infrastructure
- [x] Multi-model routing — mistral (intent/parsing), qwen3 (chat/summaries), deepseek-r1 (research), nomic-embed (vectors)
- [x] Cloudflare Tunnel documented as the recommended tunnel in deployment docs
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
