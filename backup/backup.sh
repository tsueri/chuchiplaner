#!/bin/bash
set -e

DB_PATH="${CHUCHI_DB_PATH:-/data/chuchiplaner.db}"
BACKUP_DIR="${CHUCHI_BACKUP_DIR:-/backups}"
RETENTION_DAYS="${CHUCHI_BACKUP_RETENTION:-7}"
INTERVAL_SECONDS="${CHUCHI_BACKUP_INTERVAL:-86400}"

mkdir -p "$BACKUP_DIR"

echo "Backup sidecar started. Backing up every ${INTERVAL_SECONDS}s, keeping ${RETENTION_DAYS} days."

while true; do
    timestamp=$(date +%Y-%m-%d)
    backup_file="$BACKUP_DIR/chuchiplaner-${timestamp}.db"

    if cp "$DB_PATH" "$backup_file" 2>/dev/null; then
        echo "$(date -Iseconds) backup created: $backup_file"
    else
        echo "$(date -Iseconds) backup FAILED: could not copy $DB_PATH" >&2
    fi

    find "$BACKUP_DIR" -name "chuchiplaner-*.db" -mtime +"$RETENTION_DAYS" -delete 2>/dev/null || true

    sleep "$INTERVAL_SECONDS"
done
