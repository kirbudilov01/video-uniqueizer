#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/video-uniqueizer}"
SERVICE_USER="${SERVICE_USER:-uniqueizer}"

cd "$APP_DIR"

if [ ! -f .env ]; then
  cp .env.example .env
  chmod 600 .env
  echo "Created $APP_DIR/.env. Edit BOT_TOKEN before starting."
  exit 1
fi

apt-get update
apt-get install -y python3-venv python3-pip ffmpeg redis-server
systemctl enable --now redis-server

if ! id "$SERVICE_USER" >/dev/null 2>&1; then
  useradd --system --home "$APP_DIR" --shell /usr/sbin/nologin "$SERVICE_USER"
fi

python3 -m venv "$APP_DIR/.venv"
"$APP_DIR/.venv/bin/python" -m pip install --upgrade pip
"$APP_DIR/.venv/bin/python" -m pip install -r requirements.txt
chown -R "$SERVICE_USER:$SERVICE_USER" "$APP_DIR" "$(grep '^DATA_DIR=' .env | cut -d= -f2-)"
chmod 750 "$APP_DIR" "$(grep '^DATA_DIR=' .env | cut -d= -f2-)"
chmod 600 "$APP_DIR/.env"

cat >/etc/systemd/system/video-uniqueizer-bot.service <<EOF
[Unit]
Description=Video Uniqueizer Telegram Bot
After=network-online.target redis-server.service
Wants=network-online.target

[Service]
Type=simple
User=$SERVICE_USER
WorkingDirectory=$APP_DIR
EnvironmentFile=$APP_DIR/.env
ExecStart=$APP_DIR/.venv/bin/python -m uniqueizer.bot
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

cat >/etc/systemd/system/video-uniqueizer-worker.service <<EOF
[Unit]
Description=Video Uniqueizer Worker
After=network-online.target redis-server.service
Wants=network-online.target

[Service]
Type=simple
User=$SERVICE_USER
WorkingDirectory=$APP_DIR
EnvironmentFile=$APP_DIR/.env
ExecStart=$APP_DIR/.venv/bin/python -m uniqueizer.worker
Restart=always
RestartSec=5
Nice=10
IOSchedulingClass=best-effort
IOSchedulingPriority=6

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable video-uniqueizer-bot.service video-uniqueizer-worker.service
systemctl restart video-uniqueizer-bot.service video-uniqueizer-worker.service
systemctl --no-pager --full status video-uniqueizer-bot.service video-uniqueizer-worker.service
