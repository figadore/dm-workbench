CONTAINER_ENGINE ?= $(shell if command -v docker >/dev/null 2>&1; then echo docker; else echo podman; fi)
COMPOSE := $(CONTAINER_ENGINE) compose

.PHONY: bootstrap dev-db dev-api dev-gateway stack-up stack-down stack-logs stack-smoke stack-token import-campaign-sources import-rules-sources test-integration check

bootstrap:
	./scripts/bootstrap-local-env.sh

dev-db: bootstrap
	$(COMPOSE) up -d postgres

dev-api:
	uv run --frozen uvicorn dm_assistant.api.app:create_app --factory --reload --host 127.0.0.1 --port 8000

dev-gateway:
	npm --prefix model-gateway run build
	npm --prefix model-gateway start

stack-up: bootstrap
	$(COMPOSE) up --build -d
	# Compose providers may retain a running container after rebuilding its image.
	# Recreate only code-bearing services; PostgreSQL and persistent volumes stay up.
	$(COMPOSE) up -d --force-recreate workbench model-gateway
	@port=$$(awk -F= '$$1 == "DM_WORKBENCH_PORT" {print $$2}' .env); \
		echo "Workbench: http://127.0.0.1:$${port:-8000}"
	@echo "Run 'make stack-smoke' to verify readiness."

stack-down:
	$(COMPOSE) down

stack-logs:
	$(COMPOSE) logs --follow

stack-smoke:
	@port=$$(awk -F= '$$1 == "DM_WORKBENCH_PORT" {print $$2}' .env 2>/dev/null); \
		curl --fail --silent --show-error "http://127.0.0.1:$${port:-8000}/health/ready"

stack-token: bootstrap
	@awk -F= '$$1 == "DM_API_TOKEN" {print $$2}' .env

import-campaign-sources:
	@test -n "$(SOURCE)" || (echo "usage: make import-campaign-sources SOURCE=/absolute/path" >&2; exit 2)
	CONTAINER_ENGINE=$(CONTAINER_ENGINE) ./scripts/import-sources.sh campaign "$(SOURCE)"

import-rules-sources:
	@test -n "$(SOURCE)" || (echo "usage: make import-rules-sources SOURCE=/absolute/path" >&2; exit 2)
	CONTAINER_ENGINE=$(CONTAINER_ENGINE) ./scripts/import-sources.sh rules "$(SOURCE)"

test-integration:
	CONTAINER_ENGINE=$(CONTAINER_ENGINE) ./scripts/test-integration.sh $(PYTEST_ARGS)

check:
	./scripts/check-container.sh
