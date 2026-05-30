# Project Context — Personal AI Chief of Staff
> **Purpose:** Drop this file into any new Claude Code session to resume work with full context.
> **Last Updated:** 2026-05-30
> **Session:** claude/personal-ai-chief-of-staff-xAqWZ

---

## 1. What This Project Is

A **locally-hosted, privacy-first Personal AI Executive Assistant** that operates primarily through WhatsApp. The user (Prajwal Patil — prajwalpatil522@gmail.com) communicates via WhatsApp; the AI understands text and voice notes, manages email/tasks/calendar/knowledge, conducts research, and generates briefings. All LLM inference runs locally via Ollama — no data leaves the machine.

This is a **7-phase project**. Phase 1 is fully built and merged. Phases 2–7 are planned with stubs and interfaces already in place.

---

## 2. Repository

| Field | Value |
|---|---|
| **GitHub Repo** | `prajwal-patil-hub/WhatsApp-email-agent-` |
| **PR #1** | https://github.com/prajwal-patil-hub/WhatsApp-email-agent-/pull/1 |
| **Feature Branch** | `claude/personal-ai-chief-of-staff-xAqWZ` |
| **Base Branch** | `main` |
| **Working Directory** | `/home/user/WhatsApp-email-agent-` |
| **Total Files** | 90 files, 6,626 lines (Phase 1) |

---

## 3. Tech Stack (Canonical)

| Layer | Technology | Version | Port |
|---|---|---|---|
| Workflow Engine | n8n | latest | 5678 |
| Backend API | FastAPI (Python) | 3.12 | 8000 |
| Database | PostgreSQL | 16 | 5432 |
| Cache / STM | Redis | 7-alpine | 6379 |
| Vector DB | Qdrant | latest | 6333 |
| LLM Runtime | Ollama | latest | 11434 |
| STT | faster-whisper | 1.1.1 | in-process |
| TTS | edge-tts | 6.1.18 | in-process |
| Frontend | React + Tailwind + Vite | React 18 | 3000 |
| Container | Docker Compose | v3.9 | — |

**AI Models (via Ollama):**
- `qwen3:latest` — default general assistant
- `mistral:latest` — fast intent classification
- `deepseek-r1:latest` — deep reasoning / research
- `nomic-embed-text:latest` — embeddings for vector search

---

## 4. Architecture (One-Line Flow)

```
WhatsApp → Meta API → n8n (verify + parse) → FastAPI → Executive Coordinator
→ Ollama (local LLM) → response → FastAPI → Meta API → WhatsApp reply
```

**Memory layers:**
- Short-term: Redis (24h TTL, 20-message sliding window per conversation)
- Working: PostgreSQL (goals, projects, weeks retention)
- Long-term: PostgreSQL + Qdrant (persistent, semantic search — Qdrant activated Phase 4)

---

## 5. Project Phase Status

| Phase | Name | Status | Completion |
|---|---|---|---|
| 1 | Core WhatsApp Assistant | ✅ COMPLETE | 100% |
| 2 | Email Integration | ⏳ NOT STARTED | 0% |
| 3 | Task Management | ⏳ NOT STARTED | 0% |
| 4 | Knowledge Base + Calendar | ⏳ NOT STARTED | 0% |
| 5 | Research Agent | ⏳ NOT STARTED | 0% |
| 6 | Admin Dashboard | ⏳ NOT STARTED | 0% |
| 7 | Advanced Automations | ⏳ NOT STARTED | 0% |

**Overall: 14% complete (Phase 1 of 7 done)**

---

## 6. Key Files and Their Roles

```
/home/user/WhatsApp-email-agent-/
│
├── ARCHITECTURE.md          ← Full 7-phase system design. READ THIS FIRST.
├── CONTEXT.md               ← This file. Session continuity.
├── PROGRESS.md              ← Detailed progress tracker.
├── docker-compose.yml       ← All 7 services with healthchecks.
├── .env.example             ← All required env vars (copy → .env)
├── Makefile                 ← make up / migrate / test / pull-model
│
├── backend/
│   ├── app/
│   │   ├── main.py                     ← FastAPI app factory + lifespan
│   │   ├── agents/
│   │   │   ├── coordinator.py          ← PRIMARY AGENT. Phase 1 complete.
│   │   │   ├── email_agent.py          ← STUB. Implement in Phase 2.
│   │   │   ├── task_agent.py           ← STUB. Implement in Phase 3.
│   │   │   ├── research_agent.py       ← STUB. Implement in Phase 5.
│   │   │   ├── knowledge_agent.py      ← STUB. Implement in Phase 4.
│   │   │   └── scheduling_agent.py     ← STUB. Implement in Phase 4.
│   │   ├── api/routes/
│   │   │   ├── whatsapp.py             ← Webhook ingestion. Core entry point.
│   │   │   ├── auth.py                 ← JWT token issue + revoke.
│   │   │   ├── health.py               ← /health and /health/ready
│   │   │   ├── messages.py             ← Conversation + message history.
│   │   │   └── memory.py               ← Long-term memory CRUD.
│   │   ├── core/
│   │   │   ├── config.py               ← Pydantic Settings. All env vars here.
│   │   │   ├── database.py             ← Async SQLAlchemy engine + session factory.
│   │   │   ├── security.py             ← JWT + HMAC verification.
│   │   │   └── logging.py              ← structlog setup.
│   │   ├── memory/
│   │   │   ├── short_term.py           ← Redis conversation context.
│   │   │   ├── working.py              ← PostgreSQL goals/projects.
│   │   │   └── long_term.py            ← PostgreSQL + Qdrant memories.
│   │   ├── models/db/                  ← SQLAlchemy ORM models (8 tables).
│   │   └── services/
│   │       ├── ollama.py               ← LLM client (ollama SDK + retry).
│   │       ├── whisper.py              ← Voice note transcription.
│   │       ├── whatsapp.py             ← WhatsApp Business API client.
│   │       └── audit.py                ← Append-only audit log writer.
│   ├── migrations/versions/
│   │   └── 001_initial_schema.py       ← ALL 8 tables. Run: make migrate
│   └── tests/
│       ├── unit/                        ← coordinator, memory, whisper, security
│       └── integration/                 ← health, whatsapp webhook
│
├── n8n/workflows/
│   ├── whatsapp_ingestion.json          ← Import into n8n first. Core flow.
│   └── morning_briefing.json            ← Daily 7am briefing.
│
└── frontend/src/
    ├── App.tsx                           ← Router. 5 pages wired.
    ├── pages/Dashboard.tsx              ← Health + phase roadmap view.
    └── components/Layout.tsx            ← Sidebar navigation.
```

---

## 7. Critical Design Decisions (Do Not Change Without Review)

### Background Tasks Must Create Their Own DB Session
**File:** `backend/app/api/routes/whatsapp.py`
**Rule:** FastAPI BackgroundTasks run after the request response is sent. The request-scoped `AsyncSession` (from `Depends(get_db)`) is already closed by then. Background tasks call `get_session_factory()()` directly.
```python
# CORRECT — background task creates own session
async with get_session_factory()() as db:
    await _process_message_with_db(db=db, ...)
# WRONG — session is closed when task runs
background_tasks.add_task(_process_message, db=db, ...)
```

### HMAC Verification Uses Positional Args
**File:** `backend/app/core/security.py`
**Rule:** Python's `hmac.new()` does NOT accept keyword arguments. Always use positional.
```python
# CORRECT
hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
# WRONG — raises TypeError at runtime
hmac.new(key=secret.encode(), msg=body, digestmod=hashlib.sha256)
```

### Whisper Warmup is Non-Blocking
**File:** `backend/app/main.py`
**Rule:** `warmup_whisper()` is synchronous and blocks. Must run in executor.
```python
await asyncio.get_event_loop().run_in_executor(None, warmup_whisper)
```

### Redis Singleton Uses asyncio.Lock
**File:** `backend/app/memory/short_term.py`
**Rule:** The Redis client singleton uses double-checked locking with `asyncio.Lock()` to prevent duplicate connection pools under concurrent startup.

### Audit Logs Are Append-Only
**File:** `backend/app/models/db/audit.py` and `backend/app/services/audit.py`
**Rule:** Never UPDATE or DELETE audit_logs rows in application code. They are an immutable audit trail.

---

## 8. Database Schema (Summary)

| Table | Purpose | Key Columns |
|---|---|---|
| `users` | Phone-based identity | `phone_number` (unique), `role` (user/admin) |
| `conversations` | Message threads | `user_id`, `channel` (whatsapp/email), `status` |
| `messages` | Every message in/out | `role` (user/assistant), `wa_message_id` (dedup) |
| `sessions` | JWT revocation | `token_jti` (unique), `revoked` |
| `memories` | Long-term memory | `memory_type`, `importance`, `embedding_id` (Qdrant) |
| `tasks` | Task management | `priority`, `status`, `due_date`, `recurrence` |
| `knowledge_items` | Phase 4 RAG docs | `source_type`, `content_hash` (dedup), `status` |
| `audit_logs` | Immutable trail | `action`, `user_id`, `details` (JSONB) |

**Migration:** `backend/migrations/versions/001_initial_schema.py`
**Run:** `make migrate` (or `docker compose exec backend alembic upgrade head`)

---

## 9. Agent Intent Taxonomy

The Executive Coordinator classifies every message into one of 15 intents:

| Intent | Routes To | Phase |
|---|---|---|
| `general_chat` | Coordinator (LLM direct) | 1 ✅ |
| `memory_store` | `long_term.store_memory()` | 1 ✅ |
| `memory_search` | `long_term.search_memories()` | 1 ✅ |
| `briefing` | Briefing stub | 1 ✅ |
| `email_read` | Email Agent | 2 |
| `email_draft` | Email Agent | 2 |
| `email_send` | Email Agent | 2 |
| `task_create` | Task Agent | 3 |
| `task_list` | Task Agent | 3 |
| `task_update` | Task Agent | 3 |
| `calendar_schedule` | Scheduling Agent | 4 |
| `calendar_query` | Scheduling Agent | 4 |
| `knowledge_search` | Knowledge Agent | 4 |
| `knowledge_ingest` | Knowledge Agent | 4 |
| `research` | Research Agent | 5 |

---

## 10. Environment Variables Reference

**Minimum required to run Phase 1:**
```bash
SECRET_KEY                   # openssl rand -hex 32
DATABASE_URL                 # postgresql+asyncpg://user:pass@postgres:5432/db
POSTGRES_PASSWORD            # strong password
REDIS_URL                    # redis://:password@redis:6379/0
REDIS_PASSWORD               # strong password
WHATSAPP_API_TOKEN           # Meta Developer Console
WHATSAPP_PHONE_NUMBER_ID     # Meta Developer Console
WHATSAPP_APP_SECRET          # Meta App Settings → Basic
WHATSAPP_VERIFY_TOKEN        # any random string
ADMIN_PHONE_NUMBER           # your WhatsApp number (no +)
ADMIN_SECRET                 # openssl rand -hex 24
N8N_BASIC_AUTH_PASSWORD      # n8n login password
N8N_ENCRYPTION_KEY           # openssl rand -hex 32
```

---

## 11. How to Run (Quick Reference)

```bash
# 1. Setup
cp .env.example .env          # fill in required values

# 2. Start all services
make up

# 3. Run DB migrations
make migrate

# 4. Pull AI model
make pull-model MODEL=qwen3:latest

# 5. Verify
curl http://localhost:8000/api/v1/health

# 6. Expose webhook (WhatsApp requires public HTTPS)
ngrok http 5678

# 7. Import n8n workflow
# Open http://localhost:5678 → Import n8n/workflows/whatsapp_ingestion.json

# 8. Configure Meta webhook
# Webhook URL: https://your-ngrok-url/webhook/whatsapp
# Verify Token: your WHATSAPP_VERIFY_TOKEN value
```

---

## 12. Testing

```bash
make test                     # all tests
make test-unit                # unit tests only
make test-integration         # integration tests only
```

**Test files:**
- `tests/unit/test_coordinator.py` — intent classification, routing, chat with history
- `tests/unit/test_memory.py` — all 3 memory layers
- `tests/unit/test_whisper.py` — transcription + security functions
- `tests/integration/test_health.py` — health endpoint
- `tests/integration/test_whatsapp_webhook.py` — payload parsing, HMAC, dedup

---

## 13. What To Build Next (Phase 2)

**Phase 2 = Email Integration.** The Email Agent stub is at `backend/app/agents/email_agent.py`.

Steps to implement:
1. Add Gmail OAuth2 routes to `backend/app/api/routes/` (new file: `email.py`)
2. Add email credentials to `users` table (new migration `002_email_oauth.py`)
3. Implement `EmailAgent.get_unread_summary()` using Google Gmail API
4. Implement `EmailAgent.draft_reply()` using LLM + email thread context
5. Implement `EmailAgent.send_email()` via Gmail API
6. Wire up coordinator routing: `email_read/draft/send` → EmailAgent (currently returns stub message)
7. Create n8n workflow: `n8n/workflows/email_monitor.json` (poll Gmail every 5 min)
8. Add Outlook support (Microsoft Graph API)
9. Tests: `tests/unit/test_email_agent.py`, `tests/integration/test_email_routes.py`

**New pip packages needed:**
```
google-auth-oauthlib
google-api-python-client
msal  # Microsoft auth
```

---

## 14. Coding Conventions (Follow These)

- **Python:** SQLAlchemy 2.0 mapped_column style, Pydantic v2 `model_config = ConfigDict(from_attributes=True)`, async everywhere
- **No hardcoded secrets** — always `get_settings().FIELD_NAME`
- **Every agent action** must call `await audit.log_action(db, action="agent.action", ...)` 
- **Background tasks** must create their own DB session (see §7)
- **No comments** unless the WHY is non-obvious
- **Structured logging** via `logger = get_logger(__name__)` from `app.core.logging`
- **New DB tables** go in `app/models/db/` + new Alembic migration in `migrations/versions/`
- **New API routes** go in `app/api/routes/` + registered in `app/api/router.py`

---

## 15. Git Workflow

```bash
# All work goes on the feature branch
git checkout claude/personal-ai-chief-of-staff-xAqWZ

# After implementing a phase
git add -A
git commit -m "feat: Phase N — <description>"
git push -u origin claude/personal-ai-chief-of-staff-xAqWZ
```

**PR:** Already created at https://github.com/prajwal-patil-hub/WhatsApp-email-agent-/pull/1

---

## 16. Session History Summary

| Date | Work Done |
|---|---|
| 2026-05-29 | Repository created (empty) |
| 2026-05-30 | Full Phase 1 implemented: 90 files, 6,626 lines. Architecture doc, Docker, FastAPI, all agents (coordinator complete, 5 stubs), 3-layer memory, Whisper STT, n8n workflows, React dashboard, tests. 6 bugs caught + fixed by adversarial review. PR #1 opened. |

---

*To resume in a new session: paste this file and say "Continue building the Personal AI Chief of Staff from where we left off. Read CONTEXT.md and PROGRESS.md."*
