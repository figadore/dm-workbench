#!/bin/sh
# Run PostgreSQL integration tests against an isolated disposable pgvector database.
set -eu

if [ -n "${CONTAINER_ENGINE:-}" ]; then
  container_engine=$CONTAINER_ENGINE
elif command -v docker >/dev/null 2>&1; then
  container_engine=docker
elif command -v podman >/dev/null 2>&1; then
  container_engine=podman
else
  echo "Docker or Podman is required for integration tests" >&2
  exit 2
fi

image=${DM_TEST_POSTGRES_IMAGE:-docker.io/pgvector/pgvector:0.8.1-pg16-bookworm}
container_name=${DM_TEST_POSTGRES_CONTAINER:-dm-assistant-integration-$$}
database=dm_assistant_test
user=dm_test
password=synthetic-test-password

cleanup() {
  "$container_engine" rm -f "$container_name" >/dev/null 2>&1 || true
}
trap cleanup EXIT HUP INT TERM

"$container_engine" run -d \
  --name "$container_name" \
  -e "POSTGRES_DB=$database" \
  -e "POSTGRES_USER=$user" \
  -e "POSTGRES_PASSWORD=$password" \
  -p 127.0.0.1::5432 \
  "$image" >/dev/null

attempt=0
until "$container_engine" exec "$container_name" \
  pg_isready -U "$user" -d "$database" >/dev/null 2>&1; do
  attempt=$((attempt + 1))
  if [ "$attempt" -ge 30 ]; then
    echo "Disposable PostgreSQL did not become ready" >&2
    "$container_engine" logs "$container_name" >&2 || true
    exit 1
  fi
  sleep 1
done

published=$($container_engine port "$container_name" 5432/tcp | tail -n 1)
port=${published##*:}
case "$port" in
  ''|*[!0-9]*)
    echo "Could not determine the disposable PostgreSQL host port" >&2
    exit 1
    ;;
esac

database_url="postgresql+psycopg://${user}:${password}@127.0.0.1:${port}/${database}"
if [ "$#" -eq 0 ]; then
  set -- tests/integration
fi

DM_DISABLE_DOTENV=1 \
DM_DATABASE_URL=$database_url \
DM_TEST_DATABASE_URL=$database_url \
  uv run --frozen pytest "$@"
