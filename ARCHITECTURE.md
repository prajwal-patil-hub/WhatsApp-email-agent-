# Personal AI Chief of Staff — Architecture Document

> Version 1.0 | Phase 1 Complete | 7-Phase Roadmap

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [System Overview Diagram](#system-overview-diagram)
3. [Component Descriptions](#component-descriptions)
4. [Data Flow Diagrams](#data-flow-diagrams)
5. [Database Schema](#database-schema)
6. [API Design](#api-design)
7. [n8n Workflow Descriptions](#n8n-workflow-descriptions)
8. [Security Design](#security-design)
9. [Folder Structure](#folder-structure)
10. [Implementation Roadmap](#implementation-roadmap)
11. [Technology Decisions](#technology-decisions)
12. [Operational Runbook](#operational-runbook)

---

## Executive Summary

The Personal AI Chief of Staff is a locally-hosted, privacy-first executive assistant that operates through WhatsApp as its primary interface. It processes natural language commands, manages email/tasks/calendar, maintains long-term memory of preferences and context, conducts research, and generates executive briefings.

The system uses a multi-agent architecture coordinated by an Executive Coordinator. All AI inference runs locally via Ollama, meaning no data leaves your infrastructure. The system is designed for a single-user deployment on a developer laptop or home server, with a path to multi-user via RBAC in later phases.

**Core Design Principles:**
- **Privacy first** — all LLM inference is local via Ollama
- **WhatsApp as primary UX** — no app to install, works on existing device
- **Event-driven** — n8n orchestrates external integrations
- **Modular agents** — each domain is an independent agent
- **Observable** — structured logging + audit trail on every action

---

## System Overview Diagram

```
╔══════════════════════════════════════════════════════════════════════════════╗
║                    PERSONAL AI CHIEF OF STAFF v1.0                         ║
║                         System Architecture                                  ║
╚══════════════════════════════════════════════════════════════════════════════╝

 ENTRY CHANNELS                 ORCHESTRATION           CORE ENGINE
 ───────────────                 ─────────────           ───────────
                                                    ┌─────────────────────┐
 📱 WhatsApp ──────────────┐    ┌─────────────┐    │  FastAPI Backend     │
    (Text + Voice + Media) │───►│             │───►│                     │
                           │    │  n8n        │    │  ┌───────────────┐  │
 📧 Gmail   ───────────────┤    │  Workflow   │    │  │   Executive   │  │
    (Phase 2)              │───►│  Engine     │    │  │  Coordinator  │  │
                           │    │  :5678      │◄───│  └──────┬────────┘  │
 📧 Outlook ───────────────┤    │             │    │         │           │
    (Phase 2)              │───►└─────────────┘    │  ┌──────▼────────┐  │
                           │                       │  │    Agents     │  │
 💬 Telegram ──────────────┤                       │  │ ┌───────────┐ │  │
    (Phase 2)              │                       │  │ │   Email   │ │  │
                           │                       │  │ │   Task    │ │  │
 🌐 Web Portal ────────────┘    ┌─────────────┐    │  │ │ Research  │ │  │
    React :3000 ─────────────►  │  React      │    │  │ │ Knowledge │ │  │
                                │  Dashboard  │    │  │ │ Schedule  │ │  │
                                │  :3000      │    │  │ └───────────┘ │  │
                                └─────────────┘    │  └──────┬────────┘  │
                                                   │         │           │
                                                   └─────────┼───────────┘
                                                             │
                                    ┌────────────────────────┼────────────────────────┐
                                    │         AI SERVICES    │                        │
                                    │  ┌─────────────┐  ┌───▼──────────┐             │
                                    │  │   Ollama    │  │   Whisper    │             │
                                    │  │  :11434     │  │   (STT)      │             │
                                    │  │  DeepSeek   │  │  faster-wh.  │             │
                                    │  │  Qwen3      │  └──────────────┘             │
                                    │  │  Mistral    │                               │
                                    │  │  Gemma      │  ┌──────────────┐             │
                                    │  └─────────────┘  │  Edge TTS    │             │
                                    │                   │  (TTS)       │             │
                                    │                   └──────────────┘             │
                                    └────────────────────────────────────────────────┘

 STORAGE LAYER
 ─────────────
 ┌────────────────┐   ┌────────────────┐   ┌────────────────┐
 │   PostgreSQL   │   │     Redis      │   │    Qdrant      │
 │   :5432        │   │   :6379        │   │   :6333        │
 │ • Users        │   │ • Session ctx  │   │ • Memory emb.  │
 │ • Conversations│   │ • Rate limits  │   │ • Doc. chunks  │
 │ • Messages     │   │ • Job queue    │   │ • Semantic     │
 │ • Tasks        │   │ • Pub/sub      │   │   search       │
 │ • Memories     │   └────────────────┘   └────────────────┘
 │ • Audit logs   │
 └────────────────┘
```

---

## Component Descriptions

### n8n Workflow Engine
**Role:** External integration bus and event router.

n8n receives webhooks from WhatsApp Business API, parses payloads, downloads media, and forwards structured events to the FastAPI backend. It also handles outbound flows — polling Gmail/Outlook, triggering morning briefings, and scheduling automation runs.

**Why n8n instead of custom code:** Pre-built nodes for 400+ integrations. Visual workflow editor. Built-in retry/error handling. Webhook management. Faster to wire up Gmail OAuth, Outlook, Slack than writing bespoke connectors.

### FastAPI Backend
**Role:** Core application server. Routes requests, orchestrates agents, manages state.

All business logic lives here. The API is consumed by n8n (webhook processing), the React dashboard, and can be called directly for scripting. Uses async I/O throughout for high concurrency without threads.

### Executive Coordinator Agent
**Role:** Intent classifier and request router.

Receives every processed message. Classifies intent using the local LLM. Routes to specialized agents or handles directly. Maintains conversation context. The coordinator is the only agent implemented in Phase 1; others are stubs that become real in subsequent phases.

**Intent taxonomy (Phase 1):**
- `general_chat` → handled directly by coordinator
- `email_*` → routed to Email Agent (Phase 2)
- `task_*` → routed to Task Agent (Phase 3)
- `knowledge_*` → routed to Knowledge Agent (Phase 4)
- `research_*` → routed to Research Agent (Phase 5)
- `schedule_*` → routed to Scheduling Agent (Phase 4)

### Email Agent (Phase 2)
Integrates with Gmail/Outlook via OAuth. Reads, summarizes, drafts, and sends email. Manages thread context. Extracts tasks and follow-ups automatically.

### Task Agent (Phase 3)
CRUD for tasks in PostgreSQL. Priority inference from natural language. Recurrence engine. Integration with calendar for deadline scheduling. Proactive nudges via WhatsApp.

### Research Agent (Phase 5)
Web search via SearXNG or Brave Search API. Multi-source synthesis. Executive summary generation. Citation tracking. Report export (PDF/Markdown).

### Knowledge Agent (Phase 4)
Document ingestion pipeline: PDF/DOCX/TXT → chunking → embeddings → Qdrant. Semantic search over personal knowledge base. Answer questions grounded in uploaded documents.

### Scheduling Agent (Phase 4)
Google Calendar / Outlook Calendar integration. Natural language scheduling. Conflict detection. Meeting preparation briefs. Agenda generation.

### Ollama Service
Local LLM inference server. Supports multiple models:
- `deepseek-r1` — reasoning-heavy tasks (research, analysis)
- `qwen3:latest` — general assistant, multilingual
- `mistral:latest` — fast, good for simple routing/classification
- `gemma3:latest` — lightweight, fast responses

### Whisper (faster-whisper)
Runs inside the FastAPI process as a Python library. Transcribes voice notes received via WhatsApp. Supports all Whisper model sizes (`tiny` → `large-v3`). Base model is default for balance of speed/accuracy.

### Memory System

**Short-Term (Redis)**
- Stores the last N messages of each conversation as a JSON list
- TTL: 24 hours (configurable)
- Key: `conversation:{conversation_id}:context`
- Used to maintain coherent multi-turn conversations

**Working Memory (PostgreSQL)**
- Current projects, active goals, ongoing tasks
- Queryable by agent for relevant context injection
- Retention: weeks (configurable per item)

**Long-Term Memory (PostgreSQL + Qdrant)**
- User preferences, important facts, contacts, learned behaviors
- Each memory entry has a PostgreSQL record (structured metadata) + Qdrant vector (semantic search)
- Supports CRUD + semantic search
- Importance scoring + access frequency for memory decay/promotion

---

## Data Flow Diagrams

### WhatsApp Text Message Flow

```
User sends WhatsApp message
         │
         ▼
WhatsApp Business API
         │ (HTTP POST webhook)
         ▼
n8n: WhatsApp Ingestion Workflow
  ├─ Parse payload
  ├─ Extract: phone_number, message_id, text, timestamp
  ├─ Validate webhook signature
         │
         ▼ (HTTP POST /api/v1/whatsapp/webhook)
FastAPI: WhatsApp Webhook Handler
  ├─ Verify HMAC signature
  ├─ Upsert User (by phone_number)
  ├─ Get or create Conversation
  ├─ Persist Message (role=user)
  ├─ Write Audit Log
         │
         ▼
Executive Coordinator
  ├─ Load conversation context (Redis)
  ├─ Build prompt (system + history + message)
  ├─ Call Ollama (LLM inference)
  ├─ Parse response
  ├─ Store response in context (Redis)
  ├─ Persist Message (role=assistant)
  ├─ Write Audit Log
         │
         ▼
WhatsApp Response Service
  ├─ POST https://graph.facebook.com/v18.0/{phone_id}/messages
  ├─ body: { to: phone_number, type: text, text: { body: response } }
         │
         ▼
User receives reply on WhatsApp
```

### WhatsApp Voice Note Flow

```
User sends voice note
         │
         ▼
n8n: WhatsApp Ingestion Workflow
  ├─ Detect message type = "audio"
  ├─ Extract media_id
  ├─ GET https://graph.facebook.com/v18.0/{media_id} → media_url
  ├─ Download audio file (OGG/Opus)
  ├─ POST /api/v1/whatsapp/voice (multipart: audio_file + metadata)
         │
         ▼
FastAPI: Voice Handler
  ├─ Save audio to temp file
  ├─ Whisper transcription (faster-whisper)
  ├─ Continue as text message flow with transcription
  ├─ Prepend "[Voice Note]: " to message
         │
         ▼
Executive Coordinator → Response → WhatsApp reply
```

### Memory Retrieval Flow (Long-Term)

```
Incoming message
         │
         ▼
Coordinator
  ├─ Generate embedding for message (Ollama embeddings endpoint)
  ├─ Search Qdrant (top-k similar memories)
  ├─ Fetch memory records from PostgreSQL (by IDs)
  ├─ Inject relevant memories into system prompt
  ├─ Increment access_count on retrieved memories
         │
         ▼
LLM call with enriched context
```

---

## Database Schema

### Entity Relationship Diagram

```
┌──────────────────────────────────────────────────────────────────────────┐
│                         DATABASE SCHEMA                                   │
└──────────────────────────────────────────────────────────────────────────┘

  users
  ─────
  id            UUID        PK
  phone_number  VARCHAR(20) UNIQUE NOT NULL
  name          VARCHAR(255)
  email         VARCHAR(255) UNIQUE
  role          VARCHAR(50)  DEFAULT 'user'   -- user, admin
  is_active     BOOLEAN      DEFAULT true
  preferences   JSONB        DEFAULT '{}'
  timezone      VARCHAR(50)  DEFAULT 'UTC'
  created_at    TIMESTAMPTZ  DEFAULT now()
  updated_at    TIMESTAMPTZ  DEFAULT now()

       │ 1
       │ has many
       ▼ N

  conversations
  ─────────────
  id            UUID         PK
  user_id       UUID         FK → users.id  NOT NULL
  channel       VARCHAR(50)  NOT NULL  -- whatsapp, email, telegram, web
  status        VARCHAR(50)  DEFAULT 'active'  -- active, archived
  title         VARCHAR(500)
  metadata      JSONB        DEFAULT '{}'
  created_at    TIMESTAMPTZ  DEFAULT now()
  updated_at    TIMESTAMPTZ  DEFAULT now()

  INDEX: (user_id, status, created_at DESC)

       │ 1
       │ has many
       ▼ N

  messages
  ────────
  id              UUID         PK
  conversation_id UUID         FK → conversations.id  NOT NULL
  role            VARCHAR(20)  NOT NULL  -- user, assistant, system
  content         TEXT         NOT NULL
  message_type    VARCHAR(50)  DEFAULT 'text'  -- text, voice, image, document, email
  media_url       TEXT
  transcription   TEXT                   -- populated for voice notes
  wa_message_id   VARCHAR(255)           -- WhatsApp message ID for dedup
  tokens_used     INTEGER      DEFAULT 0
  model_used      VARCHAR(100)
  processing_ms   INTEGER      DEFAULT 0
  metadata        JSONB        DEFAULT '{}'
  created_at      TIMESTAMPTZ  DEFAULT now()

  INDEX: (conversation_id, created_at ASC)
  INDEX: (wa_message_id) -- for deduplication

  ──────────────────────────────────────────────────────────────

  sessions  (JWT revocation tracking)
  ────────
  id          UUID         PK
  user_id     UUID         FK → users.id  NOT NULL
  token_jti   VARCHAR(36)  UNIQUE NOT NULL  -- JWT ID claim
  expires_at  TIMESTAMPTZ  NOT NULL
  revoked     BOOLEAN      DEFAULT false
  ip_address  VARCHAR(45)
  user_agent  TEXT
  created_at  TIMESTAMPTZ  DEFAULT now()

  INDEX: (token_jti)
  INDEX: (user_id, expires_at)

  ──────────────────────────────────────────────────────────────

  memories
  ────────
  id            UUID         PK
  user_id       UUID         FK → users.id  NOT NULL
  memory_type   VARCHAR(50)  NOT NULL  -- preference, contact, fact, goal, habit
  content       TEXT         NOT NULL
  summary       VARCHAR(500)           -- short summary for context injection
  embedding_id  VARCHAR(36)            -- Qdrant point UUID
  importance    FLOAT        DEFAULT 0.5   -- 0.0 to 1.0
  access_count  INTEGER      DEFAULT 0
  last_accessed TIMESTAMPTZ
  expires_at    TIMESTAMPTZ            -- NULL = permanent
  source        VARCHAR(100)           -- conversation_id, manual, auto
  metadata      JSONB        DEFAULT '{}'
  created_at    TIMESTAMPTZ  DEFAULT now()
  updated_at    TIMESTAMPTZ  DEFAULT now()

  INDEX: (user_id, memory_type, importance DESC)
  INDEX: (user_id, last_accessed DESC)

  ──────────────────────────────────────────────────────────────

  tasks
  ─────
  id                UUID         PK
  user_id           UUID         FK → users.id  NOT NULL
  title             VARCHAR(500) NOT NULL
  description       TEXT
  priority          VARCHAR(20)  DEFAULT 'medium'  -- low, medium, high, urgent
  status            VARCHAR(50)  DEFAULT 'pending' -- pending, in_progress, completed, cancelled
  due_date          TIMESTAMPTZ
  completed_at      TIMESTAMPTZ
  project           VARCHAR(255)
  tags              TEXT[]       DEFAULT '{}'
  recurrence        VARCHAR(100)              -- cron-like: "0 9 * * 1" = every Monday 9am
  source_channel    VARCHAR(50)
  source_message_id UUID         FK → messages.id
  reminder_sent_at  TIMESTAMPTZ
  metadata          JSONB        DEFAULT '{}'
  created_at        TIMESTAMPTZ  DEFAULT now()
  updated_at        TIMESTAMPTZ  DEFAULT now()

  INDEX: (user_id, status, priority, due_date)
  INDEX: (user_id, project, status)

  ──────────────────────────────────────────────────────────────

  knowledge_items  (Phase 4)
  ───────────────
  id            UUID         PK
  user_id       UUID         FK → users.id  NOT NULL
  title         VARCHAR(500)
  source_type   VARCHAR(50)  NOT NULL  -- pdf, docx, url, email, notion, markdown
  source_url    TEXT
  file_path     TEXT
  content_hash  VARCHAR(64)  UNIQUE     -- SHA256 for dedup
  status        VARCHAR(50)  DEFAULT 'pending'  -- pending, processing, indexed, failed
  chunk_count   INTEGER      DEFAULT 0
  metadata      JSONB        DEFAULT '{}'
  created_at    TIMESTAMPTZ  DEFAULT now()
  updated_at    TIMESTAMPTZ  DEFAULT now()

  INDEX: (user_id, source_type, status)

  ──────────────────────────────────────────────────────────────

  audit_logs
  ──────────
  id            UUID         PK  DEFAULT gen_random_uuid()
  user_id       UUID         FK → users.id  (nullable for system actions)
  action        VARCHAR(100) NOT NULL  -- coordinator.process, email.send, task.create, etc.
  resource_type VARCHAR(100)           -- message, task, memory, email
  resource_id   TEXT
  status        VARCHAR(20)  DEFAULT 'success'  -- success, failure, error
  details       JSONB        DEFAULT '{}'
  duration_ms   INTEGER
  ip_address    VARCHAR(45)
  created_at    TIMESTAMPTZ  DEFAULT now()

  INDEX: (user_id, action, created_at DESC)
  INDEX: (created_at DESC)  -- for admin dashboard
  -- No UPDATE/DELETE on audit_logs — append only
```

---

## API Design

### Base URL
`http://localhost:8000/api/v1`

### Authentication
All endpoints except `/health` and `/webhook` require `Authorization: Bearer <jwt>`.

### Endpoints

#### Health
```
GET  /health                    → 200 { status, version, uptime, services }
GET  /health/ready              → 200 | 503 (checks DB + Redis connectivity)
```

#### Auth
```
POST /auth/token                → 200 { access_token, token_type, expires_in }
     Body: { phone_number, admin_secret }
     (Admin-only bootstrap; WhatsApp users are auto-created on first message)

POST /auth/revoke               → 200
     Header: Authorization: Bearer <token>
```

#### WhatsApp Webhook
```
GET  /whatsapp/webhook          → 200 (Meta verification challenge)
     Query: hub.mode, hub.challenge, hub.verify_token

POST /whatsapp/webhook          → 200
     Body: WhatsApp Business API payload
     Header: X-Hub-Signature-256: sha256=<hmac>
     (Processes message, calls coordinator, sends reply)

POST /whatsapp/voice            → 200 { transcription, message_id }
     Body: multipart/form-data { audio: file, phone_number, message_id }
     (Transcribes voice note, processes as text)
```

#### Messages
```
GET  /messages                  → 200 { items[], total, page, size }
     Query: conversation_id?, channel?, limit=20, offset=0

GET  /messages/{id}             → 200 Message

GET  /conversations             → 200 { items[], total }
     Query: status=active, limit=20, offset=0

GET  /conversations/{id}/messages → 200 { items[], total }
```

#### Memory
```
GET  /memory                    → 200 { items[], total }
     Query: type?, query? (semantic search), limit=10

POST /memory                    → 201 Memory
     Body: { memory_type, content, importance?, expires_at? }

PUT  /memory/{id}               → 200 Memory
     Body: { content?, importance?, expires_at? }

DELETE /memory/{id}             → 204
```

#### Tasks
```
GET  /tasks                     → 200 { items[], total }
     Query: status?, priority?, project?, due_before?, limit=20

POST /tasks                     → 201 Task
     Body: { title, description?, priority?, due_date?, project? }

PUT  /tasks/{id}                → 200 Task
DELETE /tasks/{id}              → 204
```

#### Admin
```
GET  /admin/audit               → 200 { items[], total }
     Query: user_id?, action?, from?, to?, limit=50

GET  /admin/system/health       → 200 { services health map }
GET  /admin/users               → 200 { items[], total }
```

---

## n8n Workflow Descriptions

### Workflow 1: WhatsApp Message Ingestion

**Trigger:** Webhook (POST) from WhatsApp Business API

**Nodes:**
1. **Webhook Trigger** — receives incoming WhatsApp payload at `/n8n/webhook/whatsapp`
2. **HMAC Verify** (Code node) — validates `X-Hub-Signature-256` header
3. **Extract Message** (Code node) — flattens the nested WhatsApp payload structure
4. **Route by Type** (Switch node):
   - `text` → Text Processing branch
   - `audio` → Voice Note branch
   - `image` → Image branch (Phase 2)
   - `document` → Document branch (Phase 4)
5. **Text Branch:** HTTP Request → POST `/api/v1/whatsapp/webhook` with parsed payload
6. **Voice Branch:**
   - HTTP Request → GET `https://graph.facebook.com/v18.0/{media_id}` (get download URL)
   - HTTP Request → GET media_url (download audio binary)
   - HTTP Request → POST `/api/v1/whatsapp/voice` (multipart with audio)
7. **Error Handler** — on any failure, logs to audit endpoint + sends fallback message to user

### Workflow 2: Morning Executive Briefing

**Trigger:** Schedule (cron: `0 7 * * *` — 7am daily)

**Nodes:**
1. **Cron Trigger** — fires at 7:00 AM user's timezone
2. **Get User** (HTTP Request) — GET `/api/v1/admin/users` to get admin phone number
3. **Get Today's Agenda** (HTTP Request) — GET `/api/v1/tasks?status=pending&due_before=today`
4. **Get Emails** (HTTP Request) — GET `/api/v1/email/unread?priority=high` (Phase 2)
5. **Build Briefing** (Code node) — assembles briefing text from all data
6. **Send WhatsApp** (HTTP Request) — POST to WhatsApp API to send briefing to admin
7. **Log Sent** (HTTP Request) — POST `/api/v1/audit/log`

---

## Security Design

### Authentication Flow
```
Admin bootstraps via POST /auth/token with { phone_number, admin_secret }
  → Server validates admin_secret (from env var ADMIN_SECRET)
  → Creates User record if not exists
  → Returns JWT with: sub=user_id, jti=uuid4, exp=24h, role=admin

WhatsApp users:
  → Auto-created on first webhook message (no auth needed for webhook)
  → Webhook endpoint is secured by HMAC signature verification
  → Dashboard access requires JWT
```

### HMAC Webhook Verification
Every incoming WhatsApp webhook is verified:
```python
expected = hmac.new(
    key=settings.WHATSAPP_APP_SECRET.encode(),
    msg=request_body,
    digestmod=hashlib.sha256
).hexdigest()
if not hmac.compare_digest(f"sha256={expected}", header_signature):
    raise HTTPException(403)
```

### JWT Security
- Algorithm: HS256 (RS256 recommended for multi-service in Phase 6+)
- Secret: 256-bit random key in `SECRET_KEY` env var
- JTI claim: each token has a unique ID stored in `sessions` table
- Revocation: check JTI against `sessions.revoked` on every request
- Expiry: 24h default, configurable via `JWT_ACCESS_TOKEN_EXPIRE_MINUTES`

### Environment Variable Management
All secrets are in `.env` (never committed to git). Required variables validated at startup.

```
SECRET_KEY          — JWT signing secret (generate: openssl rand -hex 32)
DATABASE_URL        — postgres://user:pass@host:5432/db
WHATSAPP_API_TOKEN  — Meta App access token
WHATSAPP_APP_SECRET — Meta App secret (for HMAC verification)
WHATSAPP_PHONE_NUMBER_ID — Meta phone number ID
WHATSAPP_VERIFY_TOKEN    — Custom string for Meta webhook verification
ADMIN_PHONE_NUMBER  — Your WhatsApp number (admin bootstrap)
ADMIN_SECRET        — Secret for admin token endpoint
```

### RBAC Foundation
Two roles in Phase 1: `user`, `admin`. Extended in Phase 6:
- `user` — can only access own data (enforced by `user_id` filter on all queries)
- `admin` — can access audit logs, user management, system health

### Audit Trail
Every agent action writes an immutable `audit_logs` record. Records are append-only (no UPDATE/DELETE in application code). Useful for compliance, debugging, and behavioral analysis.

### Data Encryption (Phase 6)
- Database column encryption for `messages.content` and `memories.content` using `pgcrypto`
- File encryption for uploaded documents using AES-256
- TLS for all inter-service communication in production

---

## Folder Structure

```
whatsapp-ai-chief-of-staff/
│
├── ARCHITECTURE.md                    ← This document
├── docker-compose.yml                 ← All services (prod)
├── docker-compose.dev.yml             ← Dev overrides (hot reload)
├── .env.example                       ← Required env vars template
├── .env                               ← Local secrets (gitignored)
├── Makefile                           ← Common commands
├── .gitignore
│
├── backend/                           ← FastAPI application
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── alembic.ini
│   │
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                    ← App factory + lifespan
│   │   │
│   │   ├── agents/                    ← AI Agents
│   │   │   ├── __init__.py
│   │   │   ├── coordinator.py         ← Phase 1: COMPLETE
│   │   │   ├── email_agent.py         ← Phase 2: stub
│   │   │   ├── task_agent.py          ← Phase 3: stub
│   │   │   ├── research_agent.py      ← Phase 5: stub
│   │   │   ├── knowledge_agent.py     ← Phase 4: stub
│   │   │   └── scheduling_agent.py    ← Phase 4: stub
│   │   │
│   │   ├── api/                       ← HTTP layer
│   │   │   ├── __init__.py
│   │   │   ├── deps.py                ← FastAPI dependencies
│   │   │   ├── router.py              ← Route aggregation
│   │   │   └── routes/
│   │   │       ├── __init__.py
│   │   │       ├── auth.py
│   │   │       ├── health.py
│   │   │       ├── messages.py
│   │   │       ├── memory.py
│   │   │       ├── tasks.py
│   │   │       └── whatsapp.py
│   │   │
│   │   ├── core/                      ← Infrastructure
│   │   │   ├── __init__.py
│   │   │   ├── config.py              ← Pydantic settings
│   │   │   ├── database.py            ← Async SQLAlchemy engine
│   │   │   ├── logging.py             ← Structured logging (structlog)
│   │   │   └── security.py            ← JWT encode/decode/verify
│   │   │
│   │   ├── memory/                    ← Memory subsystem
│   │   │   ├── __init__.py
│   │   │   ├── short_term.py          ← Redis-based conversation context
│   │   │   ├── working.py             ← PostgreSQL-based project/goal state
│   │   │   └── long_term.py           ← PostgreSQL + Qdrant persistent memory
│   │   │
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── db/                    ← SQLAlchemy ORM models
│   │   │   │   ├── __init__.py
│   │   │   │   ├── base.py            ← DeclarativeBase
│   │   │   │   ├── user.py
│   │   │   │   ├── conversation.py
│   │   │   │   ├── message.py
│   │   │   │   ├── session.py
│   │   │   │   ├── memory.py
│   │   │   │   ├── task.py
│   │   │   │   ├── knowledge.py       ← Phase 4
│   │   │   │   └── audit.py
│   │   │   │
│   │   │   └── schemas/               ← Pydantic v2 schemas
│   │   │       ├── __init__.py
│   │   │       ├── auth.py
│   │   │       ├── whatsapp.py
│   │   │       ├── message.py
│   │   │       ├── memory.py
│   │   │       └── task.py
│   │   │
│   │   └── services/                  ← External service clients
│   │       ├── __init__.py
│   │       ├── ollama.py              ← Ollama LLM client
│   │       ├── whisper.py             ← faster-whisper STT
│   │       ├── edge_tts.py            ← Edge TTS (Phase 3)
│   │       ├── whatsapp.py            ← WhatsApp Business API client
│   │       └── audit.py               ← Audit log writer
│   │
│   ├── migrations/                    ← Alembic
│   │   ├── env.py
│   │   ├── script.py.mako
│   │   └── versions/
│   │       └── 001_initial_schema.py
│   │
│   └── tests/
│       ├── __init__.py
│       ├── conftest.py                ← Fixtures, test DB, mocks
│       ├── fixtures/
│       │   ├── whatsapp_messages.json ← Sample payloads
│       │   └── sample_voice.ogg       ← Test audio (gitignored if large)
│       ├── unit/
│       │   ├── __init__.py
│       │   ├── test_coordinator.py
│       │   ├── test_memory.py
│       │   ├── test_security.py
│       │   └── test_whisper.py
│       └── integration/
│           ├── __init__.py
│           ├── test_health.py
│           ├── test_whatsapp_webhook.py
│           └── test_auth.py
│
├── n8n/
│   ├── workflows/
│   │   ├── whatsapp_ingestion.json    ← Main WhatsApp workflow
│   │   ├── morning_briefing.json      ← Daily briefing workflow
│   │   ├── email_monitor.json         ← Phase 2: Gmail/Outlook monitor
│   │   ├── invoice_processor.json     ← Phase 7: Invoice automation
│   │   └── meeting_processor.json     ← Phase 7: Meeting invite automation
│   └── README.md
│
├── frontend/                          ← React + Tailwind dashboard
│   ├── package.json
│   ├── tailwind.config.js
│   ├── tsconfig.json
│   ├── vite.config.ts
│   ├── index.html
│   └── src/
│       ├── main.tsx
│       ├── App.tsx
│       ├── api/
│       │   └── client.ts
│       ├── components/
│       │   ├── Layout.tsx
│       │   ├── Sidebar.tsx
│       │   ├── ConversationList.tsx
│       │   ├── MessageThread.tsx
│       │   ├── TaskList.tsx
│       │   ├── MemoryViewer.tsx
│       │   ├── SystemHealth.tsx
│       │   └── AuditLog.tsx
│       ├── pages/
│       │   ├── Dashboard.tsx
│       │   ├── Conversations.tsx
│       │   ├── Tasks.tsx
│       │   ├── Memory.tsx
│       │   ├── Knowledge.tsx          ← Phase 4
│       │   └── Settings.tsx
│       └── types/
│           └── index.ts
│
└── docs/
    ├── phase1-setup.md                ← Getting started guide
    ├── phase2-email.md                ← Email integration guide
    ├── phase3-tasks.md
    ├── phase4-knowledge.md
    ├── phase5-research.md
    ├── phase6-dashboard.md
    ├── phase7-automations.md
    ├── api-reference.md               ← Full API docs
    ├── n8n-workflows.md               ← Workflow configuration guide
    └── security.md                    ← Security hardening guide
```

---

## Implementation Roadmap

### Phase 1 — Core WhatsApp Assistant
**Goal:** WhatsApp message in → Ollama AI response → WhatsApp reply
**Timeline:** Week 1-2

Deliverables:
- [x] Architecture document (this file)
- [x] Docker Compose (PostgreSQL, Redis, Qdrant, Ollama, FastAPI, n8n)
- [x] FastAPI backend with JWT auth, audit logging, HMAC verification
- [x] PostgreSQL schema + Alembic migrations
- [x] Executive Coordinator agent (text + voice)
- [x] Short-term memory (Redis conversation context)
- [x] Whisper voice note transcription
- [x] WhatsApp Business API integration
- [x] n8n workflow for WhatsApp ingestion
- [x] Unit + integration tests

**Exit criterion:** Send "Hello" on WhatsApp → receive an intelligent AI response within 3 seconds.

### Phase 2 — Email Integration
**Goal:** Read, summarize, draft, and send email from WhatsApp
**Timeline:** Week 3-4

Deliverables:
- Gmail OAuth2 integration (IMAP + Gmail API)
- Outlook/Office365 OAuth2 integration
- Email Agent (read, draft, send, thread awareness)
- "Summarize today's emails" command
- "Draft reply to [sender]" command
- Follow-up reminder system
- Priority email detection (urgency classification)
- n8n email monitoring workflow
- Email → PostgreSQL ingestion (for knowledge base)

### Phase 3 — Task Management
**Goal:** Create, manage, and get reminded about tasks via WhatsApp
**Timeline:** Week 5-6

Deliverables:
- Task Agent (full CRUD)
- Natural language task extraction from messages
- Priority inference ("urgent", "ASAP", "sometime" → priority levels)
- Recurring task engine (cron-based scheduler)
- Due date reminders via WhatsApp
- Project grouping
- Task → email follow-up automation
- "Show my tasks for today" briefing extension
- Proactive nudge system (overdue task alerts)

### Phase 4 — Knowledge Base + Calendar
**Goal:** Upload documents, ask questions; manage calendar
**Timeline:** Week 7-8

Deliverables:
- Knowledge Agent
- Document ingestion pipeline (PDF, DOCX, TXT, Markdown)
- Chunking (recursive character splitter, 512 tokens, 50 overlap)
- Embedding generation (Ollama embeddings endpoint)
- Qdrant indexing + semantic search
- "Summarize this PDF" → send PDF on WhatsApp → instant summary
- Long-term memory system (Qdrant + PostgreSQL)
- Scheduling Agent
- Google Calendar integration
- "Schedule meeting with X at 3pm tomorrow"
- Conflict detection
- Meeting preparation brief (agenda, attendee context)

### Phase 5 — Research Agent
**Goal:** On-demand research and report generation
**Timeline:** Week 9-10

Deliverables:
- Research Agent
- SearXNG or Brave Search API integration
- Multi-source content fetching + summarization
- Executive summary generation
- Report export (Markdown + PDF via WeasyPrint)
- Citation tracking
- "Research top AI agent frameworks" → structured report in WhatsApp
- Saved research archive in knowledge base

### Phase 6 — Admin Dashboard
**Goal:** Web UI for viewing and managing all system state
**Timeline:** Week 11-12

Deliverables:
- React + Tailwind dashboard (complete, all pages)
- Conversation viewer with message threading
- Task kanban board
- Memory CRUD interface
- Knowledge base browser
- Research report viewer
- Audit log viewer
- System health monitoring (service status, latency, token usage)
- Analytics (messages/day, tasks completed, memory items, etc.)
- Dashboard authentication (JWT + refresh tokens)
- Responsive mobile design

### Phase 7 — Advanced Automations
**Goal:** Proactive intelligence and complex workflow automations
**Timeline:** Week 13-16

Deliverables:
- Automated email classification + routing (invoice → task, meeting invite → calendar)
- Invoice processor automation (extract due date, amount, vendor → create task)
- Meeting invite processor (summarize, check conflicts, suggest accept/decline)
- Daily executive briefing (7am: calendar + emails + tasks + project updates)
- Proactive context injection ("You have a meeting in 30 min with...")
- Voice response (Edge TTS → WhatsApp voice note reply)
- Telegram, Slack, Microsoft Teams channels
- Multi-model routing (use mistral for fast responses, deepseek-r1 for research)
- Web portal (Phase 6 dashboard with public URL via Cloudflare Tunnel)
- Mobile app (React Native, Phase 3 channels bridge)

---

## Technology Decisions

### Why n8n over custom Python integrations?
n8n provides pre-built nodes for WhatsApp Business API, Gmail, Google Calendar, Outlook, Slack, and hundreds of other services. Building custom OAuth2 flows for each would take weeks. n8n's visual editor makes it easy to debug and modify workflows without code. The webhook management is production-ready.

**Trade-off:** n8n adds operational complexity (another service to maintain). For a single developer, this is acceptable given the integration speed benefit.

### Why Ollama over cloud LLMs?
Privacy: no message content leaves the local network. Cost: no per-token fees at scale. Latency: local inference can be <500ms on modern hardware (GPU). Control: swap models without code changes.

**Trade-off:** Requires a machine with sufficient RAM (16GB+ for Qwen3). Initial model download (4-20GB). Slower on CPU-only machines. For responses, 3-7 seconds on CPU, <1 second on GPU.

### Why FastAPI over Django/Flask?
Async I/O from day one. Pydantic integration for automatic validation/serialization. OpenAPI docs auto-generated. Type safety throughout. Best Python framework for AI agent backends.

**Trade-off:** More boilerplate than Flask for simple endpoints. Requires understanding async/await.

### Why PostgreSQL over SQLite?
Full JSON/JSONB support (used extensively in `metadata` columns). UUID primary keys natively. Better full-text search. Production-ready for multi-user (Phase 6). Alembic migrations work identically in dev and prod.

**Trade-off:** Requires running the PG container. For pure local use, SQLite would suffice.

### Why Redis for short-term memory?
TTL-based expiry is native. Fast in-memory reads (<1ms). Pub/sub for real-time features (Phase 6 dashboard). List/sorted-set data structures match conversation context patterns.

**Trade-off:** Additional service. Data lost on restart (acceptable for short-term context with 24h TTL).

### Why Qdrant for vector search?
Best-in-class performance. Docker-native. Filtering by payload (user_id, memory_type) is efficient. Rust implementation: low memory, fast. Python client is mature.

**Trade-off:** Not needed in Phase 1 (no knowledge base yet). Included in Docker Compose for Phase 4 readiness.

### Why faster-whisper over OpenAI Whisper?
4x faster inference on CPU. Same accuracy. Pure Python with no external server required. Runs directly in the FastAPI process as a library. Supports all standard Whisper model sizes.

**Trade-off:** Larger startup time when model loads first time. Can be mitigated by warming up on startup.

### Model Selection Guide
| Use Case | Model | Reason |
|---|---|---|
| Fast chat response | `mistral:latest` | ~3s on CPU, good quality |
| General assistant | `qwen3:latest` | Best all-around quality, multilingual |
| Complex reasoning | `deepseek-r1:latest` | Best reasoning, use for research |
| Lightweight | `gemma3:2b` | Fastest on CPU, for simple tasks |
| Embeddings | `nomic-embed-text` | Best embedding model for Ollama |

---

## Operational Runbook

### First-Time Setup
```bash
# 1. Clone and configure
cp .env.example .env
# Edit .env with your values

# 2. Start all services
make up

# 3. Run database migrations
make migrate

# 4. Pull Ollama model
make pull-model MODEL=qwen3:latest

# 5. Import n8n workflows
# Open http://localhost:5678
# Import workflows from n8n/workflows/

# 6. Configure WhatsApp webhook
# Set webhook URL in Meta Developer Console to:
# https://your-tunnel.ngrok.io/n8n/webhook/whatsapp

# 7. Test
make test
curl http://localhost:8000/api/v1/health
```

### Tunneling for WhatsApp Webhook (Local Development)
WhatsApp Business API requires a public HTTPS URL. Use ngrok or Cloudflare Tunnel:
```bash
# ngrok
ngrok http 5678  # n8n webhook port

# Cloudflare Tunnel
cloudflared tunnel --url http://localhost:5678
```

### Adding a New Ollama Model
```bash
docker exec -it ollama ollama pull mistral:latest
# Or via make:
make pull-model MODEL=mistral:latest
```

### Viewing Logs
```bash
make logs          # all services
make logs-backend  # backend only
make logs-n8n      # n8n only
```

### Backup
```bash
make backup   # dumps PostgreSQL + Qdrant snapshots to ./backups/
```
