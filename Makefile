# ==============================================================================
# ATHENA FACE - MAKEFILE
# ==============================================================================

.PHONY: help install dev hooks test lint format typecheck security check build run clean

# Default target
help:
	@echo "Athena Face - Available Commands"
	@echo "================================="
	@echo ""
	@echo "Setup:"
	@echo "  make install    - Install production dependencies"
	@echo "  make dev        - Install all dependencies (dev + prod)"
	@echo "  make hooks      - Install pre-commit hooks"
	@echo ""
	@echo "Development:"
	@echo "  make run        - Start the service locally"
	@echo "  make test       - Run all tests"
	@echo "  make test-cov   - Run tests with coverage"
	@echo ""
	@echo "Code Quality:"
	@echo "  make lint       - Run linters (ruff)"
	@echo "  make format     - Format code (black + ruff)"
	@echo "  make typecheck  - Run type checker (mypy)"
	@echo "  make security   - Run security checks (bandit)"
	@echo "  make check      - Run all checks (lint + typecheck + security)"
	@echo ""
	@echo "Docker:"
	@echo "  make build      - Build Docker image"
	@echo "  make up         - Start with Docker Compose"
	@echo "  make down       - Stop Docker Compose"
	@echo "  make logs       - Show Docker logs"
	@echo ""
	@echo "Cleanup:"
	@echo "  make clean      - Remove caches and build artifacts"

# ==============================================================================
# Setup
# ==============================================================================

install:
	pip install -r requirements.txt

dev:
	pip install -r requirements.txt
	pip install black ruff mypy bandit pytest pytest-asyncio pytest-cov pre-commit commitizen

hooks:
	pre-commit install
	pre-commit install --hook-type commit-msg
	@echo "Pre-commit hooks installed successfully!"

# ==============================================================================
# Development
# ==============================================================================

run:
	uvicorn src.main:app --host 0.0.0.0 --port 8001 --reload

test:
	pytest tests/ -v

test-cov:
	pytest tests/ -v --cov=src --cov-report=html --cov-report=term-missing

# ==============================================================================
# Code Quality
# ==============================================================================

lint:
	ruff check src/ tests/

format:
	black src/ tests/
	ruff check src/ tests/ --fix

typecheck:
	mypy src/ --ignore-missing-imports

security:
	bandit -r src/ -c pyproject.toml -ll

check: lint typecheck security
	@echo "All checks passed!"

# ==============================================================================
# Pre-commit
# ==============================================================================

pre-commit:
	pre-commit run --all-files

pre-commit-update:
	pre-commit autoupdate

# ==============================================================================
# Docker
# ==============================================================================

build:
	docker-compose build

up:
	docker-compose up -d

down:
	docker-compose down

logs:
	docker-compose logs -f athenaface_service

rebuild:
	docker-compose up -d --build

# ==============================================================================
# Database
# ==============================================================================

migrate:
	@echo "Running migrations..."
	mysql -u root -p < migrations/create_tables.sql

seed:
	@echo "Seeding database..."
	mysql -u root -p < migrations/seed_data.sql

# ==============================================================================
# Scripts
# ==============================================================================

download-models:
	python scripts/download_models.py

generate-key:
	python scripts/generate_api_keys.py

test-connection:
	python scripts/test_tenant_connection.py

# ==============================================================================
# Secrets
# ==============================================================================

secrets-scan:
	detect-secrets scan > .secrets.baseline

secrets-audit:
	detect-secrets audit .secrets.baseline

# ==============================================================================
# Cleanup
# ==============================================================================

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "htmlcov" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type f -name ".coverage" -delete 2>/dev/null || true
	@echo "Cleaned up caches and build artifacts"
