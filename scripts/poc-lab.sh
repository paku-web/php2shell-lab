#!/bin/bash
# poc-lab.sh — Setup + run
# Usage: ./scripts/poc-lab.sh [max_attempts]

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
MAX_ATTEMPTS=${1:-5}

echo "╔══════════════════════════════════════════════════════════╗"
echo "║     PHP2Shell Lab — All-in-One (Paku)                    ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""

if ! docker ps --format '{{.Names}}' | grep -q "ctf-cross-php"; then
    echo "[Step 1/2] Setting up lab..."
    bash "$SCRIPT_DIR/setup-lab.sh"
    echo ""
else
    echo "[Step 1/2] Lab already running, skipping."
    echo ""
fi

echo "[Step 2/2] Running PoC..."
bash "$SCRIPT_DIR/run-poc.sh" "$MAX_ATTEMPTS"
