#!/usr/bin/env bash
# ALBION content cleanup: delete scraped posts older than 6 months.
# Removes markdown files from disk and corresponding rows from the database.
set -euo pipefail

APP_DIR=/opt/albion
DATA_DIR=/var/lib/albion
RETENTION_DAYS="${RETENTION_DAYS:-180}"

echo "==> ALBION cleanup: removing content older than ${RETENTION_DAYS} days"

# Delete old markdown files
deleted_files=$(find "$DATA_DIR/content" -name "*.md" -mtime +"$RETENTION_DAYS" -print -delete | wc -l)
echo "    Deleted ${deleted_files} markdown files"

# Remove empty date/domain directories left behind
find "$DATA_DIR/content" -type d -empty -delete 2>/dev/null || true

# Purge matching DB rows (posts older than retention period)
cutoff=$(date -d "-${RETENTION_DAYS} days" +%Y-%m-%dT%H:%M:%S 2>/dev/null \
      || date -v-${RETENTION_DAYS}d +%Y-%m-%dT%H:%M:%S)
deleted_rows=$(sqlite3 "$DATA_DIR/albion.db" \
  "DELETE FROM posts WHERE scraped_at < '${cutoff}'; SELECT changes();")
echo "    Purged ${deleted_rows} database rows"

# Prune old poll logs too
sqlite3 "$DATA_DIR/albion.db" \
  "DELETE FROM poll_logs WHERE timestamp < '${cutoff}';"
echo "    Pruned old poll logs"

echo "==> Cleanup complete"
