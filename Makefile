.DEFAULT_GOAL := help

# ============================================================
# Help
# ============================================================
.PHONY: help
help:
	@echo ""
	@echo "  School Manager — Plataforma de Gestão Escolar"
	@echo ""
	@echo "  make setup      Install all dependencies and copy .env"
	@echo "  make dev        Start Django development server"
	@echo "  make test       Run all tests with coverage (SQLite)"
	@echo "  make test-tenant Run PostgreSQL multi-tenant isolation tests"
	@echo "  make lint       Run ruff and black checks"
	@echo "  make format     Fix code with ruff and black"
	@echo "  make migrate    Apply database migrations"
	@echo "  make makemigrations  Create new migrations"
	@echo "  make shell      Open Django shell"
	@echo "  make worker     Start Celery worker"
	@echo "  make beat       Start Celery beat scheduler"
	@echo "  make up         Start all Docker services"
	@echo "  make down       Stop all Docker services"
	@echo "  make logs       Tail Docker logs"
	@echo "  make clean      Remove __pycache__, .pytest_cache, .ruff_cache, .coverage"
	@echo ""

# ============================================================
# Setup
# ============================================================
.PHONY: setup
setup:
	pip install -r requirements-dev.txt
	@[ -f .env ] || cp .env.example .env && echo ".env created from .env.example"

# ============================================================
# Development
# ============================================================
.PHONY: dev
dev:
	python manage.py runserver 0.0.0.0:8000

.PHONY: shell
shell:
	python manage.py shell

# ============================================================
# Database
# ============================================================
.PHONY: migrate
migrate:
	python manage.py migrate

.PHONY: makemigrations
makemigrations:
	python manage.py makemigrations

# ============================================================
# Tests
# ============================================================
.PHONY: test
test:
	pytest --cov=. --cov-report=term-missing

.PHONY: test-fast
test-fast:
	pytest -x -q

.PHONY: test-tenant
test-tenant:
	DJANGO_ENV=test_pg pytest -m tenant -v

# ============================================================
# Lint & Format
# ============================================================
.PHONY: lint
lint:
	ruff check base core accounts audit teachers students guardians classes rooms agenda activities academic_calendar attendance notifications dashboard addresses scripts
	black --check base core accounts audit teachers students guardians classes rooms agenda activities academic_calendar attendance notifications dashboard addresses scripts

.PHONY: format
format:
	ruff check base core accounts audit teachers students guardians classes rooms agenda activities academic_calendar attendance notifications dashboard addresses scripts --fix
	black base core accounts audit teachers students guardians classes rooms agenda activities academic_calendar attendance notifications dashboard addresses scripts

# ============================================================
# Celery
# ============================================================
.PHONY: worker
worker:
	celery -A core.celery worker --loglevel=info

.PHONY: beat
beat:
	celery -A core.celery beat --loglevel=info

# ============================================================
# Clean
# ============================================================
.PHONY: clean
clean:
	find . -type d -name '__pycache__' -not -path './.venv/*' -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name '.pytest_cache' -not -path './.venv/*' -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name '.ruff_cache' -not -path './.venv/*' -exec rm -rf {} + 2>/dev/null || true
	rm -f .coverage
	@echo "Cache limpo."

# ============================================================
# Docker
# ============================================================
.PHONY: up
up:
	docker compose up -d

.PHONY: down
down:
	docker compose down

.PHONY: logs
logs:
	docker compose logs -f app

.PHONY: build
build:
	docker compose build
