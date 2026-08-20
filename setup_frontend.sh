#!/usr/bin/env bash
set -euo pipefail

# PC Component Parity - Frontend deployment
# Architecture:
#   Cloudflare Tunnel -> localhost:8080
#   LAN 192.168.0.0/24 -> server:8080
#
# This script intentionally uses Vite preview as requested.
# It does NOT install/configure Nginx.

PROJECT_ROOT="${PROJECT_ROOT:-/home/owner/pc_crawler_project}"
FRONTEND_DIR="${FRONTEND_DIR:-$PROJECT_ROOT/pc-price-frontend}"
SERVICE_NAME="${SERVICE_NAME:-pc-component-frontend}"
LAN_CIDR="${LAN_CIDR:-192.168.0.0/24}"
FRONTEND_PORT="${FRONTEND_PORT:-8080}"

echo "==> Frontend deployment"
echo "Project:  $PROJECT_ROOT"
echo "Frontend: $FRONTEND_DIR"
echo "LAN:      $LAN_CIDR"
echo "Port:     $FRONTEND_PORT"

if [[ ! -d "$FRONTEND_DIR" ]]; then
    echo "ERROR: Frontend directory not found: $FRONTEND_DIR"
    exit 1
fi

if ! command -v node >/dev/null 2>&1; then
    echo "ERROR: Node.js is not installed."
    exit 1
fi

if ! command -v npm >/dev/null 2>&1; then
    echo "ERROR: npm is not installed."
    exit 1
fi

if ! command -v firewall-cmd >/dev/null 2>&1; then
    echo "ERROR: firewalld/firewall-cmd is required by this deployment script."
    exit 1
fi

cd "$FRONTEND_DIR"

echo "==> Installing Node.js dependencies"
if [[ -f package-lock.json ]]; then
    npm ci
else
    npm install
fi

echo "==> Building frontend"
npm run build

if [[ ! -d "$FRONTEND_DIR/dist" ]]; then
    echo "ERROR: Vite build did not create dist/"
    exit 1
fi

echo "==> Configure firewalld"
# Only allow LAN clients to access frontend port 8080.
# Cloudflare Tunnel connects locally, so it does not need a public firewall rule.
firewall-cmd --permanent \
  --remove-port="${FRONTEND_PORT}/tcp" >/dev/null 2>&1 || true

firewall-cmd --permanent \
  --remove-rich-rule="rule family=\"ipv4\" port port=\"${FRONTEND_PORT}\" protocol=\"tcp\" accept" \
  >/dev/null 2>&1 || true

firewall-cmd --permanent \
  --add-rich-rule="rule family=\"ipv4\" source address=\"${LAN_CIDR}\" port port=\"${FRONTEND_PORT}\" protocol=\"tcp\" accept"

firewall-cmd --reload

echo "==> Installing systemd service: $SERVICE_NAME"
cat > "/etc/systemd/system/${SERVICE_NAME}.service" <<EOF
[Unit]
Description=PC Component Parity Vite Frontend
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=owner
Group=owner
WorkingDirectory=${FRONTEND_DIR}
Environment=NODE_ENV=production
ExecStart=/usr/bin/npm run preview -- --host 0.0.0.0 --port ${FRONTEND_PORT}
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now "$SERVICE_NAME"

echo
echo "==> Frontend deployment completed."
echo "LAN:              http://SERVER_IP:${FRONTEND_PORT}"
echo "Cloudflare Tunnel: http://127.0.0.1:${FRONTEND_PORT}"
echo
echo "Check:"
echo "  systemctl status ${SERVICE_NAME}"
echo "  journalctl -u ${SERVICE_NAME} -f"
