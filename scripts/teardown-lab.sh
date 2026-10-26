#!/bin/bash
# teardown-lab.sh — Bersihkan lab
# Usage: ./scripts/teardown-lab.sh

echo "=== PHP2Shell Lab Teardown ==="

docker rm -f ctf-cross-php ctf-cross-nginx 2>/dev/null && echo "[✓] Containers removed" || echo "[!] No containers found"
docker network rm ctf-cross-net 2>/dev/null && echo "[✓] Network removed" || echo "[!] No network found"

echo ""
echo "Lab stopped."
