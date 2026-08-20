#!/usr/bin/env bash
set -euo pipefail

# PC Component Parity - Backend deployment
# Architecture:
#   Cloudflare Tunnel -> localhost:8000
#   LAN 192.168.0.0/24 -> server:8000
#
# This script intentionally keeps Django runserver as requested.
# It does NOT install/configure Gunicorn or Nginx.

PROJECT_ROOT="${PROJECT_ROOT:-/home/owner/pc_crawler_project}"
BACKEND_DIR="${BACKEND_DIR:-$PROJECT_ROOT/forge_backend_server}"
VENV_DIR="${VENV_DIR:-$PROJECT_ROOT/venv}"
SERVICE_NAME="${SERVICE_NAME:-pc-component-backend}"
LAN_CIDR="${LAN_CIDR:-192.168.0.0/24}"
DJANGO_PORT="${DJANGO_PORT:-8000}"

echo "==> Backend deployment"
echo "Project: $PROJECT_ROOT"
echo "Backend: $BACKEND_DIR"
echo "LAN:     $LAN_CIDR"
echo "Port:    $DJANGO_PORT"

if [[ ! -d "$BACKEND_DIR" ]]; then
    echo "ERROR: Backend directory not found: $BACKEND_DIR"
    exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
    echo "ERROR: python3 is not installed."
    exit 1
fi

if ! command -v firewall-cmd >/dev/null 2>&1; then
    echo "ERROR: firewalld/firewall-cmd is required by this deployment script."
    exit 1
fi

if [[ ! -d "$VENV_DIR" ]]; then
    echo "==> Creating Python virtual environment"
    python3 -m venv "$VENV_DIR"
fi

PYTHON="$VENV_DIR/bin/python"
PIP="$VENV_DIR/bin/pip"
MANAGE="$BACKEND_DIR/manage.py"

if [[ ! -x "$PYTHON" ]]; then
    echo "ERROR: Python virtual environment is invalid: $VENV_DIR"
    exit 1
fi

if [[ ! -f "$BACKEND_DIR/requirements.txt" ]]; then
    echo "ERROR: requirements.txt not found: $BACKEND_DIR/requirements.txt"
    exit 1
fi

echo "==> Installing Python dependencies"
"$PIP" install --upgrade pip
"$PIP" install -r "$BACKEND_DIR/requirements.txt"

if [[ ! -f "$MANAGE" ]]; then
    echo "ERROR: manage.py not found: $MANAGE"
    exit 1
fi

cd "$BACKEND_DIR"

echo "==> Django check"
"$PYTHON" manage.py check

echo "==> Django migrations"
"$PYTHON" manage.py migrate --noinput

echo "==> Configure firewalld"
# Only allow LAN clients to access Django port 8000.
# Cloudflare Tunnel connects locally, so it does not need a public firewall rule.
firewall-cmd --permanent \
  --remove-port="${DJANGO_PORT}/tcp" >/dev/null 2>&1 || true

firewall-cmd --permanent \
  --remove-rich-rule="rule family=\"ipv4\" port port=\"${DJANGO_PORT}\" protocol=\"tcp\" accept" \
  >/dev/null 2>&1 || true

firewall-cmd --permanent \
  --add-rich-rule="rule family=\"ipv4\" source address=\"${LAN_CIDR}\" port port=\"${DJANGO_PORT}\" protocol=\"tcp\" accept"

firewall-cmd --reload

echo "==> Installing systemd service: $SERVICE_NAME"
cat > "/etc/systemd/system/${SERVICE_NAME}.service" <<EOF
[Unit]
Description=PC Component Parity Django Backend
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=owner
Group=owner
WorkingDirectory=${BACKEND_DIR}
Environment=PYTHONUNBUFFERED=1
ExecStart=${PYTHON} ${MANAGE} runserver 0.0.0.0:${DJANGO_PORT} --noreload
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now "$SERVICE_NAME"

echo
echo "==> Backend deployment completed."
echo "LAN:              http://SERVER_IP:${DJANGO_PORT}"
echo "Cloudflare Tunnel: http://127.0.0.1:${DJANGO_PORT}"
echo
echo "Check:"
echo "  systemctl status ${SERVICE_NAME}"
echo "  journalctl -u ${SERVICE_NAME} -f"
