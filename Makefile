.PHONY: help up down restart logs logs-backend logs-n8n \
        migrate migrate-create shell-backend shell-postgres \
        test test-unit test-integration lint typecheck \
        pull-model backup clean

# ──────────────────────────────────────────────────────────────────────────────
# Default
# ──────────────────────────────────────────────────────────────────────────────
help:
	@echo ""
	@echo "Personal AI Chief of Staff — Makefile"
	@echo "────────────────────────────────────────"
	@echo "  make up              Start all services"
	@echo "  make down            Stop all services"
	@echo "  make restart         Restart all services"
	@echo "  make logs            Tail all service logs"
	@echo "  make logs-backend    Tail backend logs only"
	@echo "  make migrate         Run Alembic migrations"
	@echo "  make migrate-create  Create new migration (MSG=description)"
	@echo "  make test            Run all tests"
	@echo "  make test-unit       Run unit tests only"
	@echo "  make test-integration Run integration tests only"
	@echo "  make lint            Run flake8 + isort check"
	@echo "  make typecheck       Run mypy"
	@echo "  make pull-model      Pull Ollama model (MODEL=qwen3:latest)"
	@echo "  make shell-backend   Open shell in backend container"
	@echo "  make shell-postgres  Open psql shell"
	@echo "  make backup          Backup PostgreSQL + Qdrant"
	@echo "  make clean           Remove volumes and containers"
	@echo ""

# ──────────────────────────────────────────────────────────────────────────────
# Docker operations
# ──────────────────────────────────────────────────────────────────────────────
up:
	docker compose up -d --build
	@echo "Services started. API: http://localhost:8000 | n8n: http://localhost:5678 | Dashboard: http://localhost:3000"

down:
	docker compose down

restart:
	docker compose restart

logs:
	docker compose logs -f --tail=100

logs-backend:
	docker compose logs -f --tail=100 backend

logs-n8n:
	docker compose logs -f --tail=100 n8n

# ──────────────────────────────────────────────────────────────────────────────
# Database
# ──────────────────────────────────────────────────────────────────────────────
migrate:
	docker compose exec backend alembic upgrade head

migrate-create:
	@test -n "$(MSG)" || (echo "Usage: make migrate-create MSG='your migration message'" && exit 1)
	docker compose exec backend alembic revision --autogenerate -m "$(MSG)"

# ──────────────────────────────────────────────────────────────────────────────
# Shells
# ──────────────────────────────────────────────────────────────────────────────
shell-backend:
	docker compose exec backend /bin/bash

shell-postgres:
	docker compose exec postgres psql -U $${POSTGRES_USER:-cosuser} -d $${POSTGRES_DB:-chiefofstaff}

# ──────────────────────────────────────────────────────────────────────────────
# Tests
# ──────────────────────────────────────────────────────────────────────────────
test:
	docker compose exec backend pytest tests/ -v --tb=short

test-unit:
	docker compose exec backend pytest tests/unit/ -v --tb=short

test-integration:
	docker compose exec backend pytest tests/integration/ -v --tb=short

test-local:
	cd backend && python -m pytest tests/ -v --tb=short

# ──────────────────────────────────────────────────────────────────────────────
# Code quality
# ──────────────────────────────────────────────────────────────────────────────
lint:
	docker compose exec backend flake8 app/ --max-line-length=100
	docker compose exec backend isort --check app/

typecheck:
	docker compose exec backend mypy app/ --ignore-missing-imports

format:
	docker compose exec backend black app/ tests/
	docker compose exec backend isort app/ tests/

# ──────────────────────────────────────────────────────────────────────────────
# Ollama model management
# ──────────────────────────────────────────────────────────────────────────────
pull-model:
	@test -n "$(MODEL)" || (echo "Usage: make pull-model MODEL=qwen3:latest" && exit 1)
	docker compose exec ollama ollama pull $(MODEL)

list-models:
	docker compose exec ollama ollama list

# ──────────────────────────────────────────────────────────────────────────────
# Backup
# ──────────────────────────────────────────────────────────────────────────────
backup:
	@mkdir -p backups
	@TIMESTAMP=$$(date +%Y%m%d_%H%M%S); \
	docker compose exec -T postgres pg_dump -U $${POSTGRES_USER:-cosuser} $${POSTGRES_DB:-chiefofstaff} \
		> backups/postgres_$$TIMESTAMP.sql && \
	echo "PostgreSQL backup: backups/postgres_$$TIMESTAMP.sql"

# ──────────────────────────────────────────────────────────────────────────────
# Cleanup
# ──────────────────────────────────────────────────────────────────────────────
clean:
	@echo "WARNING: This will delete all data volumes!"
	@read -p "Are you sure? [y/N] " confirm && [ "$$confirm" = "y" ] || exit 1
	docker compose down -v --remove-orphans
