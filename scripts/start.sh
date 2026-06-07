#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# Agira Production Startup Script
# Usage: ./scripts/start.sh [frontend|backend|all]
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
IMAGE_TAG="${IMAGE_TAG:-latest}"

cd "$ROOT_DIR"

log() { echo "[$(date +%H:%M:%S)] $*"; }
fail() { echo "[$(date +%H:%M:%S)] ERROR: $*" >&2; exit 1; }

# Validate environment
check_env() {
    local missing=0
    for var in API_KEY; do
        if [[ -z "${!var:-}" ]]; then
            echo "WARNING: $var not set (optional for development)"
        fi
    done
    [[ -d "$AGIRA_JOBS_DIR" ]] || mkdir -p "$AGIRA_JOBS_DIR"
    [[ -d "$AGIRA_MEMORY_DIR" ]] || mkdir -p "$AGIRA_MEMORY_DIR"
    echo "✓ Environment validated"
}

# Pull latest images
pull_images() {
    log "Pulling agira images (tag: $IMAGE_TAG)..."
    docker compose pull --quiet agira-backend agira-frontend || true
    echo "✓ Images ready"
}

# Start all services
start_all() {
    check_env
    pull_images
    log "Starting agira stack..."
    AGIRA_JOBS_DIR="${AGIRA_JOBS_DIR:-$ROOT_DIR/.agira-jobs}" \
    AGIRA_MEMORY_DIR="${AGIRA_MEMORY_DIR:-$ROOT_DIR/.agira-memory}" \
    docker compose up -d --pull always
    log "✓ All services started"
    log "  Frontend: http://localhost:3000"
    log "  Health:   http://localhost:3000/api/health"
    log "  Backend:  agira-backend (container)"
    log "  Jobs dir: $AGIRA_JOBS_DIR"
}

# Start only backend
start_backend() {
    check_env
    docker compose up -d agira-backend
    log "✓ Backend started"
}

# Start only frontend
start_frontend() {
    docker compose up -d agira-frontend
    log "✓ Frontend started"
}

# Stop all services
stop_all() {
    log "Stopping agira stack..."
    docker compose down --remove-orphans
    log "✓ All services stopped"
}

# Show status
status() {
    docker compose ps
    echo ""
    log "Health checks:"
    curl -sf http://localhost:3000/api/health 2>/dev/null && echo "  Frontend: OK" || echo "  Frontend: FAIL"
}

# Rebuild images
rebuild() {
    log "Rebuilding images..."
    docker compose build --pull agira-backend agira-frontend
    log "✓ Images rebuilt"
}

# Show logs
logs() {
    docker compose logs --tail=50 -f "$@"
}

# Run tests inside the container
test_in_container() {
    log "Running tests in agira-backend container..."
    docker compose exec agira-backend python3 -m pytest tests/ -v
}

# ── Main ──────────────────────────────────────────────────────────────────────
COMMAND="${1:-all}"

case "$COMMAND" in
    all)          start_all ;;
    backend)      start_backend ;;
    frontend)     start_frontend ;;
    stop)         stop_all ;;
    status)       status ;;
    rebuild)      rebuild ;;
    logs)         logs "${@:2}" ;;
    test)         test_in_container ;;
    *)
    echo "Usage: $0 {all|backend|frontend|stop|status|rebuild|logs|test}"
    exit 1
    ;;
esac