# --- Stage 1: Build ---
FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

# Instalar dependencias del sistema requeridas para extensiones C/Rust y red
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    ca-certificates \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Instalar dependencias puras (aprovechando cache de Docker)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

# Copiar el codigo fuente e instalar
COPY src/ ./src/
RUN uv sync --frozen --no-dev

# --- Stage 2: Runtime Rootless ---
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

# Instalar dependencias de red en runtime
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Crear usuario rootless (UID 10001) para mayor seguridad y evitar colisiones
RUN groupadd -g 10001 appgroup && \
    useradd -u 10001 -g appgroup -s /bin/bash -m appuser && \
    mkdir -p /app/data && \
    chown -R appuser:appgroup /app/data

# Copiar entorno virtual y cdigo fuente
COPY --from=builder --chown=appuser:appgroup /app/.venv /app/.venv
COPY --from=builder --chown=appuser:appgroup /app/src /app/src

USER appuser

ENTRYPOINT ["python", "-m", "radar_social.main"]
CMD ["all"]
