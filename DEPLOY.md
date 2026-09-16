# Deploying ALBION to Hetzner Cloud

ALBION runs alongside HiveHub on the existing **CX23** (2 vCPU, 4 GB RAM).
Stack: Caddy (shared, auto-HTTPS) → uvicorn (systemd) → FastAPI + SQLite.

## 1. DNS

Add records for `albion.dirtyblades.com` at your DNS provider (Hetzner DNS
or Hover):

- `A` — name `albion`, value `<server IPv4>`
- `AAAA` — name `albion`, value `<server IPv6>`

## 2. Deploy

SSH into the existing HiveHub server and run:

```bash
ssh root@<server-ip>
git clone https://github.com/astromoose/albion.git /opt/albion
DOMAIN=albion.dirtyblades.com bash /opt/albion/deploy/setup.sh
```

This installs Python 3.12, creates the `albion` user, sets up the venv,
installs systemd units (app + backup timer + cleanup timer), and appends
the ALBION block to the existing Caddy config.

## 3. Updating

After pushing to `main`:

```bash
ssh root@<server-ip> 'bash /opt/albion/deploy/update.sh'
```

## 4. Backups

Daily SQLite backup to `/var/lib/albion/backups/` with 14-day retention
(via `albion-backup.timer`). Pull a copy:

```bash
scp root@<server-ip>:/var/lib/albion/backups/albion-daily.sqlite3 .
```

## 5. Content cleanup

Monthly timer (`albion-cleanup.timer`) deletes scraped markdown files and
database rows older than 180 days. Override retention with:

```bash
RETENTION_DAYS=365 bash /opt/albion/deploy/albion-cleanup.sh
```

## 6. Data layout

```
/opt/albion/          # app code (git repo)
/var/lib/albion/
  albion.db           # SQLite database
  content/            # scraped markdown files
  backups/            # daily snapshots
/etc/albion.env       # environment (root:root 600)
```

The app directory symlinks `content/` and `albion.db` into `/var/lib/albion/`.

## Operations

```bash
systemctl status albion               # app status
journalctl -u albion -f               # app logs
systemctl list-timers albion-*        # backup + cleanup schedule
systemctl start albion-cleanup        # manual cleanup run
```

## Shared Caddy

setup.sh appends to `/etc/caddy/Caddyfile` (doesn't overwrite). The
resulting file has both HiveHub and ALBION blocks:

```
hivehub.dirtyblades.com {
    encode gzip
    reverse_proxy 127.0.0.1:9292
}

albion.dirtyblades.com {
    encode gzip
    reverse_proxy 127.0.0.1:8420
}
```
