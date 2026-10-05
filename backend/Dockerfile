# Stage 1: builder - install deps into a venv
FROM python:3.11-slim AS builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps into a venv
COPY backend/requirements.txt .
RUN python -m venv /opt/venv && \
    /opt/venv/bin/pip install --upgrade pip && \
    /opt/venv/bin/pip install --no-cache-dir -r requirements.txt

# Stage 2: runtime - minimal image, non-root user
FROM python:3.11-slim AS runtime

# Non-root user
RUN groupadd -r appuser && useradd -r -g appuser -d /app -s /sbin/nologin appuser

# Install only runtime system deps (libpq for asyncpg)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Copy the venv from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

ENV PYTHONPATH=/app

# Copy application code
COPY --chown=appuser:appuser . .

USER appuser

EXPOSE 8000

# Health check (calls the /health endpoint)
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["uvicorn", "backend.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
