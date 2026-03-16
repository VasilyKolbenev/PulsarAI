.PHONY: install dev test lint format build docker clean help

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

install: ## Install package in editable mode
	pip install -e ".[dev,ui]"

dev: ## Start dev server (backend + frontend)
	@echo "Starting backend on :8888 and frontend on :5173..."
	@python -m uvicorn pulsar_ai.ui.app:create_app --factory --reload --port 8888 &
	@cd ui && npm run dev

test: ## Run test suite
	python -m pytest tests/ --ignore=tests/test_data.py -x

test-cov: ## Run tests with coverage report
	python -m pytest tests/ --ignore=tests/test_data.py -x \
		--cov=pulsar_ai --cov-report=term-missing --cov-report=html

lint: ## Run linters (ruff + black check)
	ruff check src/ tests/
	black --check src/ tests/

format: ## Auto-format code
	black src/ tests/
	ruff check --fix src/ tests/

build: ## Build frontend
	cd ui && npm run build

docker: ## Build Docker image
	docker build -t pulsar-ai .

docker-up: ## Start with docker-compose
	docker compose up -d

docker-down: ## Stop docker-compose
	docker compose down

clean: ## Remove build artifacts
	rm -rf dist/ build/ *.egg-info .pytest_cache htmlcov .coverage
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
