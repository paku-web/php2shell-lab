#!/bin/bash
# run-poc.sh — Jalankan PoC dengan retry
# Usage: ./scripts/run-poc.sh [max_attempts]

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PORT=18166
MAX_ATTEMPTS=${1:-5}
TARGET="http://127.0.0.1:$PORT/php-version.php"
POC="$SCRIPT_DIR/../poc/php2shell_poc.py"

echo "=== PHP2Shell PoC Runner (Paku) ==="
echo "Target: $TARGET"
echo "PoC: $POC"
echo "Max attempts: $MAX_ATTEMPTS"
echo ""

# Verify lab up
if ! curl -s --max-time 5 "$TARGET" | grep -q "PHP 8.4.26"; then
    echo "[✗] Lab not running. Run setup-lab.sh first."
    exit 1
fi

# Verify PoC exists
if [ ! -f "$POC" ]; then
    echo "[✗] PoC not found: $POC"
    exit 1
fi

# Retry loop
for attempt in $(seq 1 $MAX_ATTEMPTS); do
    echo "─── Attempt $attempt/$MAX_ATTEMPTS ───"
    OUTPUT=$(python3 "$POC" --url "$TARGET" 2>&1) || true
    echo "$OUTPUT"
    echo ""

    if echo "$OUTPUT" | grep -q "execution_proof_verified"; then
        echo "[✓] SUCCESS on attempt $attempt"
        exit 0
    fi

    echo "[!] Retry..."
    sleep 2
done

echo "[✗] All $MAX_ATTEMPTS attempts failed"
exit 1
