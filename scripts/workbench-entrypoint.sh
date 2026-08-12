#!/bin/sh
set -eu

if [ "${DM_RUN_MIGRATIONS:-true}" = "true" ]; then
  alembic upgrade head
fi

exec "$@"
