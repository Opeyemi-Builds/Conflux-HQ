# syntax=docker/dockerfile:1
FROM --platform=linux/amd64 python:3.12-slim AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# Final runtime stage
FROM --platform=linux/amd64 python:3.12-slim AS runner

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Create non-root system user and data directory for SQLite persistence
RUN groupadd -g 10001 conflux && \
    useradd -u 10001 -g conflux -s /bin/bash conflux && \
    mkdir -p /data && \
    chown -R conflux:conflux /data /app

COPY --chown=conflux:conflux . /app

USER conflux

EXPOSE 8000

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DATABASE_URL="sqlite:////data/conflux.db"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

