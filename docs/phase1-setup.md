# Phase 1 Setup Guide — Core WhatsApp Assistant

This guide walks you through setting up the Personal AI Chief of Staff from scratch.

## Prerequisites

- Docker Desktop (Mac/Windows) or Docker Engine + Compose (Linux)
- A Meta Developer account with a WhatsApp Business App
- A phone with WhatsApp for testing
- ngrok (for exposing local webhook) or Cloudflare Tunnel

---

## Step 1: Configure Environment

```bash
cp .env.example .env
```

Edit `.env` and fill in the required values:

| Variable | Where to find it |
|---|---|
| `SECRET_KEY` | Run: `openssl rand -hex 32` |
| `POSTGRES_PASSWORD` | Choose a strong password |
| `WHATSAPP_API_TOKEN` | Meta Developer Console → App → WhatsApp → API Setup |
| `WHATSAPP_PHONE_NUMBER_ID` | Meta Developer Console → App → WhatsApp → API Setup |
| `WHATSAPP_VERIFY_TOKEN` | Choose any random string (e.g., `openssl rand -hex 16`) |
| `WHATSAPP_APP_SECRET` | Meta Developer Console → App Settings → Basic |
| `ADMIN_PHONE_NUMBER` | Your WhatsApp number (no `+`, e.g., `14155551234`) |
| `ADMIN_SECRET` | Choose a strong secret: `openssl rand -hex 24` |
| `N8N_BASIC_AUTH_PASSWORD` | Choose a strong password |
| `N8N_ENCRYPTION_KEY` | Run: `openssl rand -hex 32` |

---

## Step 2: Start All Services

```bash
make up
```

This starts:
- PostgreSQL (port 5432)
- Redis (port 6379)
- Qdrant (port 6333)
- Ollama (port 11434)
- FastAPI backend (port 8000)
- n8n (port 5678)
- React dashboard (port 3000)

Wait ~60 seconds for all services to be healthy.

---

## Step 3: Run Database Migrations

```bash
make migrate
```

---

## Step 4: Pull Ollama Model

```bash
make pull-model MODEL=qwen3:latest
```

This downloads the Qwen3 model (~4GB). For faster responses, also pull:
```bash
make pull-model MODEL=mistral:latest
```

---

## Step 5: Verify Backend is Running

```bash
curl http://localhost:8000/api/v1/health
# Expected: {"status": "ok", "version": "1.0.0", ...}
```

---

## Step 6: Set Up ngrok Tunnel

WhatsApp requires a public HTTPS URL for the webhook.

```bash
# Install ngrok: https://ngrok.com/download
ngrok http 5678
# Note the HTTPS URL: https://abc123.ngrok.io
```

---

## Step 7: Import n8n Workflows

1. Open http://localhost:5678
2. Login with your `N8N_BASIC_AUTH_USER` and `N8N_BASIC_AUTH_PASSWORD`
3. Click "+" → "Import from File"
4. Import `n8n/workflows/whatsapp_ingestion.json`
5. Configure environment variables in n8n:
   - `WHATSAPP_APP_SECRET` → your WhatsApp app secret
   - `WHATSAPP_API_TOKEN` → your WhatsApp API token
   - `WHATSAPP_API_VERSION` → `v18.0`
   - `WHATSAPP_PHONE_NUMBER_ID` → your phone number ID
   - `BACKEND_URL` → `http://backend:8000`
   - `ADMIN_PHONE_NUMBER` → your WhatsApp number
6. Activate the workflow

---

## Step 8: Configure WhatsApp Webhook in Meta Console

1. Go to [Meta Developer Console](https://developers.facebook.com)
2. Navigate to your App → WhatsApp → Configuration
3. Set Webhook URL to: `https://your-ngrok-url.ngrok.io/webhook/whatsapp`
4. Set Verify Token to the value of `WHATSAPP_VERIFY_TOKEN` in your `.env`
5. Subscribe to `messages` field
6. Click "Verify and Save"

---

## Step 9: Test End-to-End

Send a WhatsApp message to your test number:
```
Hello, what can you do for me?
```

Expected response within 5-10 seconds (CPU inference):
```
Hello! I'm your AI Chief of Staff. I can help you with...
```

---

## Step 10: Run Tests

```bash
make test
```

---

## Troubleshooting

**Backend not starting:** Check `make logs-backend` — likely a missing env var. The startup validator will print which variables are missing.

**Ollama timeout:** If LLM inference takes too long, use a smaller model:
```
OLLAMA_DEFAULT_MODEL=mistral:latest
```

**WhatsApp webhook not receiving messages:** 
1. Check ngrok is running and URL is correct in Meta console
2. Check n8n workflow is Active
3. Check HMAC signature — `WHATSAPP_APP_SECRET` must match Meta App Secret exactly

**Redis connection failed:** Check `REDIS_PASSWORD` matches in docker-compose and .env.
