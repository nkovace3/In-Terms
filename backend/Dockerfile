FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim AS base

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1

# Install dependencies first (separate layer, cached while only app code changes)
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-install-project --no-dev

# Now copy the rest of the app and install it
COPY . .
RUN uv sync --locked --no-dev

EXPOSE 8000

CMD ["sh", "-c", "uv run uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
