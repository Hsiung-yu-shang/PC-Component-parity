#!/bin/bash

USER_NAME="owner" # your non-root username
PROJECT_ROOT="/home/$USER_NAME/pc_crawler_project"
DJANGO_DIR="$PROJECT_ROOT/forge_backend_server"
VENV_DIR="$PROJECT_ROOT/venv"
SERVICE_NAME="django_server"

if [ "$EUID" -ne 0 ]; then 
  echo "Error: Run this script with sudo or root privileges"
  exit 1
fi

echo "Starting automated Django development environment deployment..."

echo "[1/5] Installing system packages (Python-devel, MySQL-devel)..."
dnf install -y python3-devel mysql-devel gcc pkgconfig policycoreutils-python-utils

echo "[2/5] Installing Python dependencies..."
if [ ! -d "$VENV_DIR" ]; then
    echo "Creating virtual environment..."
    python3 -m venv "$VENV_DIR"
fi
source "$VENV_DIR/bin/activate"
pip install --upgrade pip
pip install django mysqlclient djangorestframework django-cors-headers django-filter requests

echo "[3/5] Configuring Systemd service (django_server)..."
cat <<EOF > /etc/systemd/system/${SERVICE_NAME}.service
[Unit]
Description=Django Backend Server (Development Mode)
After=network.target

[Service]
User=$USER_NAME
Group=$USER_NAME
WorkingDirectory=$DJANGO_DIR
ExecStart=$VENV_DIR/bin/python3 $DJANGO_DIR/manage.py runserver 0.0.0.0:8000
Restart=always

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now $SERVICE_NAME

echo "[4/5] Configuring firewall (opening port 8000)..."
if command -v firewall-cmd &> /dev/null; then
    firewall-cmd --permanent --add-port=8000/tcp
    firewall-cmd --reload
    echo "Firewall rules updated: Port 8000 open"
else
    echo "Warning: firewalld not detected, skipping firewall configuration"
fi

echo "[5/5] Configuring SELinux to permissive mode..."
sed -i 's/^SELINUX=enforcing/SELINUX=permissive/' /etc/selinux/config
setenforce 0

echo "=========================================="
echo "Development environment deployment complete!"
echo "=========================================="
echo "Check service status:"
echo "   systemctl status $SERVICE_NAME"
echo ""
echo "Backend running at: http://192.168.0.242:8000/api/products/"
echo "=========================================="