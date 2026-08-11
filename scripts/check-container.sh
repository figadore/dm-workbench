#!/bin/sh
# Start a disposable *_test PostgreSQL and run the complete gate in Python 3.12.
set -eu

CONTAINER_ENGINE=${CONTAINER_ENGINE:-podman}
PROJECT_NAME=${DM_CHECK_PROJECT_NAME:-dm-assistant-check-$$}
POSTGRES_PORT=${DM_TEST_POSTGRES_PORT:-55432}
POSTGRES_DB=dm_assistant_test
POSTGRES_USER=dm_test
POSTGRES_PASSWORD=synthetic-test-password
RUNNER_IMAGE=ghcr.io/astral-sh/uv:0.9.5-python3.12-bookworm

compose() {
  POSTGRES_DB=$POSTGRES_DB \
  POSTGRES_USER=$POSTGRES_USER \
  POSTGRES_PASSWORD=$POSTGRES_PASSWORD \
  POSTGRES_PORT=$POSTGRES_PORT \
    "$CONTAINER_ENGINE" compose -p "$PROJECT_NAME" "$@"
}

cleanup() {
  compose down -v >/dev/null 2>&1 || true
}
trap cleanup EXIT HUP INT TERM

compose up -d postgres
attempt=0
until compose exec -T postgres \
  pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB" >/dev/null 2>&1; do
  attempt=$((attempt + 1))
  if [ "$attempt" -ge 30 ]; then
    echo "PostgreSQL did not become healthy" >&2
    compose logs postgres >&2 || true
    exit 1
  fi
  sleep 1
done

workspace=$(pwd)
database_url="postgresql+psycopg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB}"
"$CONTAINER_ENGINE" run --rm \
  --network "${PROJECT_NAME}_default" \
  -e UV_LINK_MODE=copy \
  -e DM_ENVIRONMENT=test \
  -e "DM_DATABASE_URL=$database_url" \
  -e "DM_TEST_DATABASE_URL=$database_url" \
  -e 'DM_SOURCE_ROOTS=["/workspace/packages/dungeon-engine/tests/fixtures"]' \
  -e DM_ASSET_ROOT=/workspace/.data/check-assets \
  -e DM_SCRATCH_ROOT=/workspace/.data/check-scratch \
  -e DM_API_TOKEN=aggregate-test-token-000000000000000 \
  -e DM_SESSION_SECRET=aggregate-session-secret-000000000000 \
  -v "$workspace:/workspace" \
  -v dm-assistant-dev-venv:/workspace/.venv \
  -w /workspace \
  "$RUNNER_IMAGE" \
  ./scripts/check.sh
