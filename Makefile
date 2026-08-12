CONTAINER_ENGINE ?= podman
COMPOSE := $(CONTAINER_ENGINE) compose

.PHONY: dev-db dev-api dev-gateway stack-up stack-down stack-logs stack-smoke check

dev-db:
	$(COMPOSE) up -d postgres

dev-api:
	uv run --frozen uvicorn dm_assistant.api.app:create_app --factory --reload --host 127.0.0.1 --port 8000

dev-gateway:
	npm --prefix model-gateway run build
	npm --prefix model-gateway start

stack-up:
	$(COMPOSE) up --build -d

stack-down:
	$(COMPOSE) down

stack-logs:
	$(COMPOSE) logs --follow

stack-smoke:
	curl --fail --silent --show-error http://127.0.0.1:8000/health/ready

check:
	./scripts/check-container.sh
