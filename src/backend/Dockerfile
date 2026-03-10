FROM python:3.11-slim

WORKDIR /app

# Install system dependencies needed for asyncpg (libpq) and cryptography (libffi, openssl)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    libffi-dev \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy project descriptor first (layer cache: re-install only when deps change)
COPY pyproject.toml .

# Install Python dependencies (without the app source - install in editable mode after)
RUN pip install --no-cache-dir -e . 2>/dev/null || \
    pip install --no-cache-dir \
        fastapi \
        uvicorn[standard] \
        sqlalchemy \
        alembic \
        asyncpg \
        pydantic \
        pydantic-settings \
        python-jose[cryptography] \
        passlib[bcrypt] \
        cryptography \
        httpx \
        structlog \
        prometheus-client \
        anyio \
        python-multipart \
        email-validator

# Copy application source and migrations
COPY app/ app/
COPY migrations/ migrations/

# Re-run pip install to register the package properly (idempotent)
RUN pip install --no-cache-dir -e .

# Create non-root user for running the application
RUN useradd -m -u 1000 -s /bin/bash bugpilot \
    && chown -R bugpilot:bugpilot /app

USER bugpilot

# Expose the application port
EXPOSE 8000

# Health check - calls the liveness endpoint
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# Default command - single worker; use --workers N for multi-process
# Set WEB_CONCURRENCY env var for dynamic worker count
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
