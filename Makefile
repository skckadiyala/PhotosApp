.PHONY: help up down dev logs build migrate seed scan clean shell-backend shell-db

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

up: ## Start all services in production mode
	docker compose up -d

down: ## Stop all services
	docker compose down

dev: ## Start in development mode with hot reload
	docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build

logs: ## Tail logs from all services
	docker compose logs -f

build: ## Build all Docker images
	docker compose build

migrate: ## Run database migrations
	docker compose exec backend sh -c 'PYTHONPATH=/app alembic upgrade head'

seed: ## Create initial admin user + ensure tables
	docker compose exec backend python -m app.scripts.seed

scan: ## Trigger full photo library scan
	docker compose exec backend sh -c 'PYTHONPATH=/app python -m app.scripts.scan'

detect-faces: ## Run face detection on all unprocessed photos
	docker compose exec backend sh -c 'PYTHONPATH=/app python -m app.services.face_detector'

cluster-faces: ## Run DBSCAN clustering on face embeddings
	docker compose exec backend sh -c 'PYTHONPATH=/app python -m app.services.face_cluster'

shell-backend: ## Open shell in backend container
	docker compose exec backend bash

shell-db: ## Open psql shell
	docker compose exec postgres psql -U $${POSTGRES_USER} -d $${POSTGRES_DB}

clean: ## Remove all containers, volumes, and images
	@echo "This will delete all data including the database. Are you sure? [y/N]"
	@read ans && [ $${ans:-N} = y ] && docker compose down -v --rmi all || echo "Cancelled"
