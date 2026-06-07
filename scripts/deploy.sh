#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# Agira Production Deploy Script
# Run on your server: curl -fsSL https://raw.githubusercontent.com/.../deploy.sh | bash
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail

AGIRA_VERSION="${AGIRA_VERSION:-latest}"
AGIRA_DIR="${AGIRA_DIR:-/opt/agira}"

echo "═══════════════════════════════════════"
echo "  Agira Production Deploy"
echo "  Version: $AGIRA_VERSION"
echo "═══════════════════════════════════════"

# Check prerequisites
check_prereqs() {
    for cmd in docker docker-compose git; do
        if ! command -v $cmd &> /dev/null; then
            echo "ERROR: $cmd is required but not installed."
            exit 1
        fi
    done
    echo "✓ Prerequisites OK"
}

# Create directory and pull latest
setup() {
    echo "Setting up Agira at $AGIRA_DIR..."
    sudo mkdir -p "$AGIRA_DIR"
    sudo chown $(id -u):$(id -g) "$AGIRA_DIR"
    cd "$AGIRA_DIR"

    if [[ -d .git ]]; then
        git pull origin main
    else
        git clone https://github.com/akhileshdasari2004/hackthon1.git "$AGIRA_DIR"
        cd "$AGIRA_DIR"
    fi
    echo "✓ Code updated"
}

# Create data directories
setup_data_dirs() {
    echo "Creating data directories..."
    mkdir -p "${AGIRA_JOBS_DIR:-$AGIRA_DIR/.agira-jobs}"
    mkdir -p "${AGIRA_MEMORY_DIR:-$AGIRA_DIR/.agira-memory}"
    mkdir -p "${AGIRA_SETTINGS_DIR:-$AGIRA_DIR/.agira/settings}"
    echo "✓ Data directories ready"
    echo "  Jobs:    ${AGIRA_JOBS_DIR:-$AGIRA_DIR/.agira-jobs}"
    echo "  Memory:  ${AGIRA_MEMORY_DIR:-$AGIRA_DIR/.agira-memory}"
}

# Create .env from template
setup_env() {
    if [[ -f "$AGIRA_DIR/.env" ]]; then
        echo "⚠ .env already exists — not overwriting"
    else
        if [[ -f "$AGIRA_DIR/.env.production" ]]; then
            cp "$AGIRA_DIR/.env.production" "$AGIRA_DIR/.env"
            echo "⚠ Created .env from .env.production template"
            echo "  ⚠ IMPORTANT: Edit $AGIRA_DIR/.env and set API_KEY"
        else
            echo "WARNING: No .env or .env.production found"
        fi
    fi
}

# Pull Docker images
pull_images() {
    echo "Pulling Docker images..."
    export IMAGE_TAG="${AGIRA_VERSION}"
    docker compose pull agira-backend agira-frontend agira-sandbox 2>/dev/null || true
    echo "✓ Images pulled"
}

# Start services
start() {
    echo "Starting Agira services..."
    export IMAGE_TAG="${AGIRA_VERSION}"
    export AGIRA_JOBS_DIR="${AGIRA_JOBS_DIR:-$AGIRA_DIR/.agira-jobs}"
    export AGIRA_MEMORY_DIR="${AGIRA_MEMORY_DIR:-$AGIRA_DIR/.agira-memory}"
    docker compose up -d --pull always
    echo "✓ Services started"
}

# Health check
health_check() {
    echo "Running health checks..."
    sleep 5
    for i in {1..10}; do
        if curl -sf http://localhost:3000/api/health &>/dev/null; then
            echo "✓ Frontend is healthy"
            break
        fi
        echo "  Waiting for frontend... ($i/10)"
        sleep 3
    done
    docker compose ps
}

# Show status
status() {
    echo ""
    echo "═══════════════════════════════════════"
    echo "  Agira Status"
    echo "═══════════════════════════════════════"
    docker compose ps
    echo ""
    echo "  Frontend: http://localhost:3000"
    echo "  Health:   http://localhost:3000/api/health"
    echo ""
    echo "To view logs:   cd $AGIRA_DIR && docker compose logs -f"
    echo "To stop:        cd $AGIRA_DIR && docker compose down"
    echo "To restart:     cd $AGIRA_DIR && ./scripts/start.sh all"
    echo ""
}

# ── Main ──────────────────────────────────────────────────────────────────────
check_prereqs
setup
setup_data_dirs
setup_env
pull_images
start
health_check
status

echo "═══════════════════════════════════════"
echo "  ✓ Deploy Complete!"
echo "═══════════════════════════════════════"