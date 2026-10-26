#!/bin/bash
# setup-lab.sh — Setup PHP2Shell Alpine Lab
# Usage: ./scripts/setup-lab.sh

set -e

LAB_DIR="$HOME/php2shell-alpine-lab"
PORT=18166

echo "=== PHP2Shell Alpine Lab Setup ==="
echo "Lab directory: $LAB_DIR"
echo "Port: $PORT"
echo ""

# Cleanup lama
if docker ps -a --format '{{.Names}}' | grep -q "ctf-cross-php\|ctf-cross-nginx"; then
    echo "[*] Cleaning up existing containers..."
    docker rm -f ctf-cross-php ctf-cross-nginx 2>/dev/null || true
fi
if docker network ls --format '{{.Name}}' | grep -q "ctf-cross-net"; then
    docker network rm ctf-cross-net 2>/dev/null || true
fi

# Cipta folder
mkdir -p "$LAB_DIR/public"
cd "$LAB_DIR"

# Fail 1: public/php-version.php
cat > public/php-version.php <<'PHPEOF'
<?php
header('Content-Type: text/plain');
echo 'PHP ', PHP_VERSION, "\n";
echo 'PID: ', getmypid(), "\n";
PHPEOF

# Fail 2: print-flag
cat > print-flag <<'SHEOF'
#!/bin/sh
printf '%s\n' 'LOCAL_DUMMY_WIF_NEVER_USE'
SHEOF
chmod +x print-flag

# Fail 3: nginx.conf
cat > nginx.conf <<'NGXEOF'
events {}
http {
    server {
        listen 80;
        server_name _;
        location / {
            proxy_pass http://ctf-cross-php:8000;
            proxy_http_version 1.1;
            proxy_set_header Host $host;
        }
    }
}
NGXEOF

echo "[+] Files created."
echo ""

# Buat network
echo "[*] Creating network..."
docker network create ctf-cross-net

# Container PHP (Alpine, 4 workers)
echo "[*] Starting PHP container (Alpine 8.4.26)..."
docker run -d --name ctf-cross-php --network ctf-cross-net \
  --read-only --tmpfs /tmp:rw,size=32m,mode=1777 --memory 1g \
  -v "$LAB_DIR/public:/app:ro" \
  -v "$LAB_DIR/print-flag:/usr/local/bin/print-flag:ro" \
  -e PHP_CLI_SERVER_WORKERS=4 \
  php:8.4.26-fpm-alpine3.23 php -S 0.0.0.0:8000 -t /app

# Container nginx
echo "[*] Starting nginx container..."
docker run -d --name ctf-cross-nginx --network ctf-cross-net \
  -p 127.0.0.1:$PORT:80 \
  -v "$LAB_DIR/nginx.conf:/etc/nginx/nginx.conf:ro" \
  nginx:1.27-alpine

# Tunggu ready
echo "[*] Waiting for containers to be ready..."
sleep 5

# Verify
echo ""
echo "=== Verify ==="
if curl -s --max-time 5 "http://127.0.0.1:$PORT/php-version.php" | grep -q "PHP 8.4.26"; then
    echo "[✓] Lab is UP"
    curl -s "http://127.0.0.1:$PORT/php-version.php"
    echo ""
    echo "=== Lab ready ==="
    echo "URL: http://127.0.0.1:$PORT/php-version.php"
else
    echo "[✗] Lab failed to start. Check logs:"
    echo "  docker logs ctf-cross-php"
    echo "  docker logs ctf-cross-nginx"
    exit 1
fi
