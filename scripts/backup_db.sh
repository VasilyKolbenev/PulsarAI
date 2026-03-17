#!/usr/bin/env bash
# Pulsar AI — SQLite database backup script
#
# Usage:
#   ./scripts/backup_db.sh [db_path] [backup_dir]
#
# Defaults:
#   db_path:    data/pulsar.db
#   backup_dir: backups/
#
# Retention: keeps last 7 daily backups

set -euo pipefail

DB_PATH="${1:-data/pulsar.db}"
BACKUP_DIR="${2:-backups}"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
RETENTION_DAYS=7

# Validate source database exists
if [ ! -f "$DB_PATH" ]; then
    echo "ERROR: Database not found at $DB_PATH"
    exit 1
fi

# Create backup directory
mkdir -p "$BACKUP_DIR"

# Perform hot backup using SQLite's .backup command (safe for WAL mode)
BACKUP_FILE="$BACKUP_DIR/pulsar_${TIMESTAMP}.db"
sqlite3 "$DB_PATH" ".backup '$BACKUP_FILE'"

# Compress the backup
gzip "$BACKUP_FILE"
BACKUP_FILE="${BACKUP_FILE}.gz"

# Report
SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
echo "Backup created: $BACKUP_FILE ($SIZE)"

# Cleanup old backups (keep last RETENTION_DAYS days)
find "$BACKUP_DIR" -name "pulsar_*.db.gz" -mtime +${RETENTION_DAYS} -delete 2>/dev/null || true
REMAINING=$(find "$BACKUP_DIR" -name "pulsar_*.db.gz" | wc -l)
echo "Retention: $REMAINING backups kept (max ${RETENTION_DAYS} days)"
