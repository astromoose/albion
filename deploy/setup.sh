#!/usr/bin/env bash
# ALBION setup on an existing Hetzner CX23 running alongside HiveHub.
# Run as root:  DOMAIN=albion.dirtyblades.com bash /opt/albion/deploy/setup.sh
set -euo pipefail

DOMAIN="${DOMAIN:-albion.dirtyblades.com}"
APP_DIR=/opt/albion
DATA_DIR=/var/lib/albion
echo "==> ALBION setup for ${DOMAIN}"

echo "==> Installing system packages"
apt-get update -q
DEBIAN_FRONTEND=noninteractive apt-get install -qy \
  python3 python3-venv python3-dev \
  build-essential git libsqlite3-dev sqlite3 pkg-config curl

echo "==> Creating albion user and directories"
id -u albion &> /dev/null || useradd --system --home-dir "$APP_DIR" --shell /usr/sbin/nologin albion
mkdir -p "$DATA_DIR/backups" "$DATA_DIR/content"

echo "==> Fetching application"
if [ ! -d "$APP_DIR/.git" ]; then
  git clone https://github.com/astromoose/albion.git "$APP_DIR"
fi
chown -R albion:albion "$APP_DIR" "$DATA_DIR"

echo "==> Creating virtualenv and installing"
sudo -u albion -H sh -c "
  cd $APP_DIR
  python3 -m venv .venv
  .venv/bin/pip install --upgrade pip
  .venv/bin/pip install -e .
"

echo "==> Writing /etc/albion.env"
if [ ! -f /etc/albion.env ]; then
  cat > /etc/albion.env <<EOF
ALBION_DB=$DATA_DIR/albion.db
ALBION_CONTENT=$DATA_DIR/content
NTFY_TOPIC=albion-posts
EOF
  chmod 600 /etc/albion.env
fi

echo "==> Symlinking data paths"
# Point app's content dir and db to the persistent data directory
sudo -u albion -H sh -c "
  ln -sfn $DATA_DIR/content $APP_DIR/content
  ln -sfn $DATA_DIR/albion.db $APP_DIR/albion.db
"

echo "==> Installing systemd units"
cp "$APP_DIR/deploy/albion.service" /etc/systemd/system/
cp "$APP_DIR/deploy/albion-backup.service" /etc/systemd/system/
cp "$APP_DIR/deploy/albion-backup.timer" /etc/systemd/system/
cp "$APP_DIR/deploy/albion-cleanup.service" /etc/systemd/system/
cp "$APP_DIR/deploy/albion-cleanup.timer" /etc/systemd/system/
systemctl daemon-reload

echo "==> Adding ALBION to Caddy config"
# Append ALBION block to existing Caddyfile if not already present
if ! grep -q "$DOMAIN" /etc/caddy/Caddyfile 2>/dev/null; then
  echo "" >> /etc/caddy/Caddyfile
  sed "s/^ALBION_DOMAIN/${DOMAIN}/" "$APP_DIR/deploy/Caddyfile" >> /etc/caddy/Caddyfile
fi

echo "==> Starting services"
systemctl enable --now albion albion-backup.timer albion-cleanup.timer
systemctl reload caddy || systemctl restart caddy

echo
echo "==> Done. Checks:"
systemctl --no-pager --lines 0 status albion | head -3
sleep 2
curl -s -o /dev/null -w "    local app responds: HTTP %{http_code}\n" http://127.0.0.1:8420/
echo "    Once DNS for ${DOMAIN} points here, Caddy will fetch a TLS cert"
echo "    automatically on first request: https://${DOMAIN}"
