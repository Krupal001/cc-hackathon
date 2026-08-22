FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINKER=copy \
    UV_PYTHON_DOWNLOADS=never

COPY backend/pyproject.toml backend/uv.lock ./

RUN uv sync --frozen --no-install-project --no-dev

COPY backend/src/ src/
COPY backend/alembic.ini ./
COPY backend/alembic/ alembic/

RUN uv sync --frozen --no-dev

FROM python:3.12-slim-bookworm

WORKDIR /app

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/src /app/src
COPY --from=builder /app/alembic.ini /app/alembic.ini
COPY --from=builder /app/alembic /app/alembic
COPY --from=builder /app/pyproject.toml /app/pyproject.toml

EXPOSE 8000

CMD ["uvicorn", "codesentinel.main:app", "--host", "0.0.0.0", "--port", "8000"]
