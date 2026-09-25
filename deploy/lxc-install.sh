#!/usr/bin/env bash
set -Eeuo pipefail

# Debian 12 / Ubuntu 24.04 systemd LXC; run as root with an existing .env path.
if [[ ${EUID} -ne 0 ]]; then
  echo '請在 LXC 的 root shell 執行此腳本。' >&2
  exit 2
fi
if [[ $# -ne 1 ]]; then
  echo '用法：bash lxc-install.sh /root/pcpart.env' >&2
  exit 2
fi
if [[ ! -f $1 ]]; then
  echo "找不到設定檔：$1。請先依 README 建立 .env，填好資料庫連線與密鑰。" >&2
  exit 2
fi
if grep -Eq '^(SECRET_KEY=replace-with|DB_USER=your_|DB_PASSWORD=your_|DB_HOST=your_|SECRET_KEY=$|DB_USER=$|DB_PASSWORD=$|DB_HOST=$)' "$1"; then
  echo "設定檔 $1 仍有範例值或空白必要欄位，請先編輯後再部署。" >&2
  exit 2
fi
ENV_INPUT=$(realpath "$1")
APP_DIR=/opt/pcpart
BACKEND="$APP_DIR/pc_crawler_project/forge_backend_server"
FRONTEND="$APP_DIR/pc-price-frontend"
REPO=https://github.com/Hsiung-yu-shang/PC-Component-parity.git
REPO_REF=${PCPART_REF:-main}

if ! command -v apt-get >/dev/null || ! command -v systemctl >/dev/null; then
  echo 'This installer requires a Debian/Ubuntu systemd LXC.' >&2
  exit 2
fi

apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y ca-certificates curl gnupg git \
  python3 python3-venv python3-dev build-essential pkg-config default-libmysqlclient-dev nginx

if ! command -v node >/dev/null || [[ $(node -v | cut -d. -f1 | tr -d v) -lt 20 ]]; then
  curl -fsSL https://deb.nodesource.com/setup_22.x -o /tmp/pcpart-nodesource.sh
  bash /tmp/pcpart-nodesource.sh
  DEBIAN_FRONTEND=noninteractive apt-get install -y nodejs
fi

if ! id pcpart >/dev/null 2>&1; then
  useradd --system --home-dir "$APP_DIR" --shell /usr/sbin/nologin pcpart
fi
if [[ ! -d "$APP_DIR/.git" ]]; then
  git clone --branch "$REPO_REF" "$REPO" "$APP_DIR"
else
  git -C "$APP_DIR" fetch origin "$REPO_REF"
  if git -C "$APP_DIR" show-ref --verify --quiet "refs/heads/$REPO_REF"; then
    git -C "$APP_DIR" switch "$REPO_REF"
    git -C "$APP_DIR" pull --ff-only origin "$REPO_REF"
  else
    git -C "$APP_DIR" switch --track -c "$REPO_REF" "origin/$REPO_REF"
  fi
fi

install -m 0640 -o root -g pcpart "$ENV_INPUT" "$BACKEND/.env"
install -d -m 0700 -o pcpart -g pcpart /var/lib/pcpart
python3 -m venv "$APP_DIR/.venv"
"$APP_DIR/.venv/bin/pip" install --upgrade pip
"$APP_DIR/.venv/bin/pip" install --upgrade -r "$BACKEND/requirements.txt"
cd "$FRONTEND"
npm ci
npm run build
cd "$BACKEND"
"$APP_DIR/.venv/bin/python" manage.py check --deploy
"$APP_DIR/.venv/bin/python" manage.py migrate --noinput
"$APP_DIR/.venv/bin/python" manage.py collectstatic --noinput

cat >/etc/systemd/system/pcpart-api.service <<EOF
[Unit]
Description=PC Part Price API
After=network-online.target
Wants=network-online.target

[Service]
User=pcpart
Group=pcpart
WorkingDirectory=$BACKEND
Environment=SYNC_STATE_DIR=/var/lib/pcpart
NoNewPrivileges=true
UMask=0077
ExecStart=$APP_DIR/.venv/bin/gunicorn forge_backend_server.wsgi:application --bind 127.0.0.1:8000 --workers 1 --threads 4 --timeout 60
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

cat >/etc/systemd/system/pcpart-sync.service <<EOF
[Unit]
Description=PC Part Price source synchronization
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
User=pcpart
Group=pcpart
WorkingDirectory=$BACKEND
Environment=SYNC_STATE_DIR=/var/lib/pcpart
NoNewPrivileges=true
UMask=0077
ExecStart=$APP_DIR/.venv/bin/python manage.py sync_products
EOF

cat >/etc/systemd/system/pcpart-sync.timer <<'EOF'
[Unit]
Description=Refresh PC part prices every six hours

[Timer]
OnCalendar=*-*-* 03,09,15,21:00:00
Persistent=true
RandomizedDelaySec=15m
Unit=pcpart-sync.service

[Install]
WantedBy=timers.target
EOF

cat >/etc/nginx/sites-available/pcpart <<EOF
limit_req_zone \$binary_remote_addr zone=pcpart_api:10m rate=10r/s;
limit_req_zone \$binary_remote_addr zone=pcpart_sync:1m rate=1r/m;
server {
    listen 8080;
    server_tokens off;
    client_max_body_size 64k;
    add_header X-Content-Type-Options nosniff always;
    add_header Referrer-Policy strict-origin-when-cross-origin always;
    add_header X-Frame-Options DENY always;
    location ~ /\. { deny all; }
    location = /api/sync/ {
        limit_req zone=pcpart_sync burst=2 nodelay;
        limit_req_status 429;
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_set_header X-Real-IP \$remote_addr;
    }
    server_name _;
    root $FRONTEND/dist;
    index index.html;

    location ~ ^/(api|admin)/ {
        limit_req zone=pcpart_api burst=40 nodelay;
        limit_req_status 429;
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_set_header X-Real-IP \$remote_addr;
    }
    location /static/ { alias $BACKEND/staticfiles/; }
    location / { try_files \$uri \$uri/ /index.html; }
}
EOF
ln -sfn /etc/nginx/sites-available/pcpart /etc/nginx/sites-enabled/pcpart
nginx -t
systemctl daemon-reload
systemctl enable --now pcpart-api.service pcpart-sync.timer nginx
systemctl restart pcpart-api.service nginx
curl -fsS http://127.0.0.1:8080/ >/dev/null
echo 'Installed. Point the Cloudflare Tunnel frontend origin to http://<LXC-IP>:8080.'
echo 'Check: systemctl status pcpart-api pcpart-sync.timer; journalctl -u pcpart-sync -n 100'
