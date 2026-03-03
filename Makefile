.PHONY: dev stop test test-backend test-frontend lint lint-backend lint-frontend build migrate migrate-create clean help

help: ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

dev: ## Start all services with Docker Compose
	docker compose up -d

stop: ## Stop all services
	docker compose down

test: test-backend test-frontend ## Run all tests

test-backend: ## Run backend tests with coverage
	cd backend && python -m pytest --cov --cov-report=term-missing -q

test-frontend: ## Run frontend tests
	cd frontend && npm run test:run

lint: lint-backend lint-frontend ## Run all linters

lint-backend: ## Lint Python code with Ruff
	ruff check backend/

lint-frontend: ## Lint TypeScript code with ESLint
	cd frontend && npm run lint

build: ## Build all Docker images
	docker compose build --parallel

migrate: ## Run database migrations
	cd backend/gateway && alembic upgrade head

migrate-create: ## Create new migration (usage: make migrate-create MSG="description")
	cd backend/gateway && alembic revision --autogenerate -m "$(MSG)"

clean: ## Remove build artifacts and caches
	find backend -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find backend -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	rm -rf frontend/node_modules/.cache frontend/dist
