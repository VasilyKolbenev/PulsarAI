#!/usr/bin/env bash
# Auto-restart dev servers (backend + frontend) with resilience.
# Usage: bash scripts/dev.sh

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
LOG_DIR="$PROJECT_DIR/logs"
mkdir -p "$LOG_DIR"

BACKEND_LOG="$LOG_DIR/backend.log"
FRONTEND_LOG="$LOG_DIR/frontend.log"
RESTART_DELAY=3

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() { echo -e "${GREEN}[dev]${NC} $(date '+%H:%M:%S') $*"; }
warn() { echo -e "${YELLOW}[dev]${NC} $(date '+%H:%M:%S') $*"; }
err() { echo -e "${RED}[dev]${NC} $(date '+%H:%M:%S') $*"; }

BACKEND_PID=""
FRONTEND_PID=""

cleanup() {
    log "Shutting down dev servers..."
    [ -n "$BACKEND_PID" ] && kill "$BACKEND_PID" 2>/dev/null && log "Backend stopped"
    [ -n "$FRONTEND_PID" ] && kill "$FRONTEND_PID" 2>/dev/null && log "Frontend stopped"
    exit 0
}

trap cleanup SIGINT SIGTERM EXIT

start_backend() {
    log "Starting backend (FastAPI) on port 8888..."
    cd "$PROJECT_DIR"
    python -c "from pulsar_ai.ui.app import create_app; import uvicorn; uvicorn.run(create_app(), host='127.0.0.1', port=8888)" \
        >> "$BACKEND_LOG" 2>&1 &
    BACKEND_PID=$!
    log "Backend started (PID: $BACKEND_PID)"
}

start_frontend() {
    log "Starting frontend (Vite) on port 5173..."
    cd "$PROJECT_DIR"
    node --max-old-space-size=512 ui/node_modules/vite/bin/vite.js ui \
        --port 5173 --host 127.0.0.1 \
        >> "$FRONTEND_LOG" 2>&1 &
    FRONTEND_PID=$!
    log "Frontend started (PID: $FRONTEND_PID)"
}

monitor() {
    local name=$1
    local pid_var=$2
    local start_fn=$3
    local pid=${!pid_var}

    if [ -n "$pid" ] && ! kill -0 "$pid" 2>/dev/null; then
        err "$name crashed (was PID: $pid). Restarting in ${RESTART_DELAY}s..."
        sleep "$RESTART_DELAY"
        $start_fn
    fi
}

# Initial start
start_backend
start_frontend

log "Dev servers running. Press Ctrl+C to stop."
log "Backend log: $BACKEND_LOG"
log "Frontend log: $FRONTEND_LOG"

# Monitor loop
while true; do
    sleep 5
    monitor "Backend" BACKEND_PID start_backend
    monitor "Frontend" FRONTEND_PID start_frontend
done
