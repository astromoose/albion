#!/usr/bin/env bash
# ALBION update: pull latest main, reinstall, restart. Run as root.
set -euo pipefail

APP_DIR=/opt/albion

echo "==> Updating ALBION"
sudo -u albion -H sh -c "cd $APP_DIR && git pull --ff-only && .venv/bin/pip install -e . --quiet"

# Pick up any changed units/Caddyfile
cp "$APP_DIR/deploy/albion.service" /etc/systemd/system/
cp "$APP_DIR/deploy/albion-backup.service" /etc/systemd/system/
cp "$APP_DIR/deploy/albion-backup.timer" /etc/systemd/system/
cp "$APP_DIR/deploy/albion-cleanup.service" /etc/systemd/system/
cp "$APP_DIR/deploy/albion-cleanup.timer" /etc/systemd/system/
systemctl daemon-reload

systemctl restart albion
sleep 2
systemctl --no-pager --lines 0 status albion | head -3
curl -s -o /dev/null -w "==> app responds: HTTP %{http_code}\n" http://127.0.0.1:8420/
