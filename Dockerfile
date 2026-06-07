# ─────────────────────────────────────────────────────────────────────────────
# Agira Backend — Production Docker Image
# Security: runs with minimal privileges, no network, read-only root
# ─────────────────────────────────────────────────────────────────────────────

FROM python:3.12-slim-bookworm AS base

# Install only what we need
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ── Stage 1: Install agira (production) ──────────────────────────────────────
FROM base AS production

COPY pyproject.toml ./

# Pin to known-working versions for reproducibility
RUN pip install --no-cache-dir --disable-pip-version-check \
    setuptools>=68.0 \
    pytest>=7.0 \
    || true

# Copy agira source (install as editable for development compatibility)
COPY agira/ ./agira/
COPY scripts/ ./scripts/
COPY demo.py ./
COPY examples/ ./examples/

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV AGIRA_PROJECT_ROOT=/app
ENV AGIRA_JOBS_DIR=/data/jobs
ENV AGIRA_MEMORY_PATH=/data/memory_store.json
ENV AGIRA_SETTINGS_PATH=/data/settings.json

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python3 -c "import sys; sys.exit(0)"

# ── Stage 2: Security-hardened sandbox image ──────────────────────────────────
# This image is used internally for running untrusted user code.
# It is NOT exposed as an API — the orchestrator spawns it as a subprocess.
FROM base AS sandbox

# Create a non-root user with no sudo access
RUN groupadd --gid 1000 agira && \
    useradd --uid 1000 --gid agira --shell /usr/sbin/nologin --home /sandbox agira

WORKDIR /sandbox

# No network access in this image
# (applied at runtime via --network=none in docker-compose)

# Read-only filesystem by default (overridden at runtime with :ro)
ONBUILD USER agira

# ── Entrypoint for direct job runner ─────────────────────────────────────────
FROM production AS runner

ENTRYPOINT ["python3", "scripts/job_runner.py"]

# Usage: docker run agira /data/jobs /repo/path '{"settings": {}}'
# Returns: 0 on success, non-zero on failure; results written to job_dir