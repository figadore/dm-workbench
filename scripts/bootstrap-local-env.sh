#!/bin/sh
# Idempotently create local Compose secrets without exposing fixed credentials.
set -eu

ENV_FILE=${DM_ENV_FILE:-.env}
CREATED_FILE=false

if [ ! -e "$ENV_FILE" ]; then
  umask 077
  cat >"$ENV_FILE" <<'EOF'
# Generated local runtime configuration. Do not commit this file.
POSTGRES_DB=dm_assistant
POSTGRES_USER=dm_assistant
POSTGRES_PORT=5432
DM_WORKBENCH_PORT=8000
EOF
  CREATED_FILE=true
elif [ ! -f "$ENV_FILE" ]; then
  echo "$ENV_FILE exists but is not a regular file" >&2
  exit 1
fi

chmod 0600 "$ENV_FILE"

random_hex() {
  if command -v openssl >/dev/null 2>&1; then
    openssl rand -hex 32
  elif command -v python3 >/dev/null 2>&1; then
    python3 -c 'import secrets; print(secrets.token_hex(32))'
  else
    echo "openssl or python3 is required to generate local secrets" >&2
    exit 1
  fi
}

current_value() {
  key=$1
  awk -F= -v key="$key" '$1 == key {sub(/^[^=]*=/, ""); value=$0} END {print value}' "$ENV_FILE"
}

ensure_secret() {
  key=$1
  value=$(current_value "$key")
  case "$value" in
    ""|replace-*)
      generated=$(random_hex)
      temporary="${ENV_FILE}.tmp.$$"
      awk -F= -v key="$key" '$1 != key {print}' "$ENV_FILE" >"$temporary"
      printf '%s=%s\n' "$key" "$generated" >>"$temporary"
      chmod 0600 "$temporary"
      mv "$temporary" "$ENV_FILE"
      GENERATED_KEYS="${GENERATED_KEYS}${GENERATED_KEYS:+ }$key"
      ;;
  esac
}

GENERATED_KEYS=
ensure_secret POSTGRES_PASSWORD
ensure_secret DM_API_TOKEN
ensure_secret DM_SESSION_SECRET
ensure_secret DM_MODEL_GATEWAY_INTERNAL_TOKEN

if [ "$CREATED_FILE" = true ]; then
  echo "Created $ENV_FILE with persistent random local secrets."
elif [ -n "$GENERATED_KEYS" ]; then
  echo "Generated missing local secrets in $ENV_FILE: $GENERATED_KEYS"
else
  echo "Local runtime configuration is ready: $ENV_FILE"
fi

case " $GENERATED_KEYS " in
  *" DM_API_TOKEN "*)
    echo "Browser/API login token: $(current_value DM_API_TOKEN)"
    ;;
  *)
    echo "Use 'make stack-token' if you need the browser/API login token."
    ;;
esac
