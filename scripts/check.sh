#!/bin/sh
# One frozen contributor/CI gate. Run inside the documented Python 3.12 container.
set -eu

uv sync --all-packages --all-groups --frozen
rm -rf /tmp/dm-assistant-build
uv build --all-packages --out-dir /tmp/dm-assistant-build >/dev/null

uv run --frozen dm --help >/dev/null
uv run --frozen dm-dungeon --help >/dev/null
uv run --frozen dm-dungeon validate \
  packages/dungeon-engine/tests/fixtures/sunken_archive.v1.json

if [ -n "${DM_TEST_DATABASE_URL:-}" ]; then
  database_without_query=${DM_TEST_DATABASE_URL%%\?*}
  case "$database_without_query" in
    */*_test) ;;
    *)
      echo "refusing migration gate: DM_TEST_DATABASE_URL must name a *_test database" >&2
      exit 2
      ;;
  esac
  export DM_DATABASE_URL="$DM_TEST_DATABASE_URL"
  uv run --frozen alembic downgrade base
  uv run --frozen alembic upgrade head
  uv run --frozen pytest tests/integration
  uv run --frozen alembic downgrade base
  uv run --frozen alembic upgrade head
  uv run --frozen dm doctor --json
else
  echo "database gate skipped: set safety-gated DM_TEST_DATABASE_URL" >&2
fi

uv run --frozen pytest tests/unit
uv run --frozen pytest packages/dungeon-engine/tests
uv run --frozen ruff check .
uv run --frozen ruff format --check .
uv run --frozen mypy src
uv run --frozen mypy packages/dungeon-engine/src
git -c safe.directory="$PWD" diff --check
