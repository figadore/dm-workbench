FROM ghcr.io/astral-sh/uv:0.9.5-python3.12-bookworm-slim

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:${PATH}"

WORKDIR /app

RUN groupadd --gid 10001 workbench \
    && useradd --uid 10001 --gid workbench --create-home --shell /usr/sbin/nologin workbench

COPY . .

RUN uv sync --frozen --no-dev --all-packages \
    && chmod 0755 /app/scripts/workbench-entrypoint.sh \
    && mkdir -p /data/assets /data/scratch \
    && chown -R workbench:workbench /app /data

USER workbench

EXPOSE 8000

ENTRYPOINT ["/app/scripts/workbench-entrypoint.sh"]
CMD ["uvicorn", "dm_assistant.api.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
