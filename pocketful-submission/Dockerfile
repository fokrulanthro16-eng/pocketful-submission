# ==============================================================================
# Multi-Stage Production Dockerfile for Pocketful Autonomous Fintech Engine
# Base: python:3.11-slim | Hardened Non-Root Execution | Zero Runtime Dependencies
# ==============================================================================

# Stage 1: Build & Dependency Resolution
FROM python:3.11-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libc6-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install/deps -r requirements.txt

# Stage 2: Hardened Runtime Container
FROM python:3.11-slim AS runtime

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app/deps/lib/python3.11/site-packages:$PYTHONPATH \
    PATH=/app/deps/bin:$PATH \
    PORT=8080

# Create dedicated non-root banking-grade system user
RUN groupadd -g 10001 appgroup && \
    useradd -u 10001 -g appgroup -s /sbin/nologin -d /app appuser

# Copy isolated dependencies from builder stage
COPY --from=builder /install/deps /app/deps

# Copy application source code (Stage-4 Enterprise Build)
COPY stage-4/app /app/app

# Ownership and security hardening
RUN chown -R appuser:appgroup /app
USER appuser:appgroup

EXPOSE 8080

# Zero-Sum Ledger Healthcheck Probe
HEALTHCHECK --interval=15s --timeout=5s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request, json; res = json.loads(urllib.request.urlopen('http://127.0.0.1:8080/health').read()); exit(0 if res.get('status') == 'ok' else 1)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
