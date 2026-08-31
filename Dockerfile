# Stage 1: Builder
FROM python:3.11-slim AS builder

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Instalación optimizada para caché
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

# Instalación final
COPY src/ ./src/
RUN uv sync --frozen --no-dev

# Stage 2: Runtime Rootless
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# Inicializar entorno rootless y garantizar permisos de directorios montables
RUN groupadd -g 1000 appgroup && \
    useradd -u 1000 -g appgroup -s /bin/bash -m appuser && \
    mkdir -p /app/data && \
    chown -R appuser:appgroup /app/data

# Copiar artefactos de compilación asignando directamente la propiedad a appuser
COPY --from=builder --chown=appuser:appgroup /app/.venv /app/.venv
COPY --from=builder --chown=appuser:appgroup /app/src /app/src

USER appuser

CMD ["python", "-m", "src.main"]
