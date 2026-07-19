.DEFAULT_GOAL := help

VENV := .venv
VENV_BIN := $(VENV)/bin

# ============================================================
# Help
# ============================================================
.PHONY: help
help:
	@echo ""
	@echo "  School Manager — Plataforma de Gestão Escolar"
	@echo ""
	@echo "  make setup      Create the Python 3.13 virtualenv and install dependencies"
	@echo "  make dev        Start Django development server"
	@echo "  make test       Run all tests with coverage (SQLite)"
	@echo "  make test-tenant Run PostgreSQL multi-tenant isolation tests"
	@echo "  make test-ui    Run Chromium visual contract tests"
	@echo "  make check-ui   Validate canonical page and grid contracts"
	@echo "  make lint       Run ruff and black checks"
	@echo "  make format     Fix code with ruff and black"
	@echo "  make migrate    Apply shared multi-tenant migrations"
	@echo "  make reset-dev  Recreate development databases and local media"
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
	python3.13 -m venv $(VENV)
	$(VENV_BIN)/python -m pip install --upgrade pip
	$(VENV_BIN)/python -m pip install --require-hashes -r requirements-dev.lock

# ============================================================
# Development
# ============================================================
.PHONY: dev
dev:
	$(VENV_BIN)/python manage.py runserver 0.0.0.0:8000

.PHONY: shell
shell:
	$(VENV_BIN)/python manage.py shell

# ============================================================
# Database
# ============================================================
.PHONY: migrate
migrate:
	$(VENV_BIN)/python manage.py migrate_schemas --shared

.PHONY: makemigrations
makemigrations:
	$(VENV_BIN)/python manage.py makemigrations

.PHONY: reset-dev
reset-dev:
	sh scripts/reset_dev.sh

# ============================================================
# Tests
# ============================================================
.PHONY: test
test:
	$(VENV_BIN)/pytest --cov=. --cov-report=term-missing

.PHONY: test-fast
test-fast:
	$(VENV_BIN)/pytest -x -q

.PHONY: test-tenant
test-tenant:
	DJANGO_ENV=test_pg $(VENV_BIN)/pytest -m tenant -v

.PHONY: test-ui
test-ui:
	DJANGO_ALLOW_ASYNC_UNSAFE=true DJANGO_UI_TEST_DB=/tmp/school-manager-playwright.sqlite3 $(VENV_BIN)/pytest -m ui --browser chromium --tracing=retain-on-failure --screenshot=only-on-failure

.PHONY: check-ui
check-ui:
	$(VENV_BIN)/python scripts/check_ui_contracts.py

# ============================================================
# Lint & Format
# ============================================================
.PHONY: lint
lint:
	$(VENV_BIN)/ruff check .
	$(VENV_BIN)/black --check .

.PHONY: format
format:
	$(VENV_BIN)/ruff check . --fix
	$(VENV_BIN)/black .

# ============================================================
# Celery
# ============================================================
.PHONY: worker
worker:
	$(VENV_BIN)/celery -A core.celery worker --loglevel=info

.PHONY: beat
beat:
	$(VENV_BIN)/celery -A core.celery beat --loglevel=info

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
