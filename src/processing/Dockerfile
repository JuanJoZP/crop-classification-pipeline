FROM python:3.10-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    gdal-bin \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

COPY .python-version .
COPY pyproject.toml uv.lock ./
COPY src/ src/

RUN uv venv && \
    uv sync --frozen --no-dev --package processing

CMD ["sh", "-c", "uv run --package processing python -m ${PROCESSING_STEP:-bronze}.main"]