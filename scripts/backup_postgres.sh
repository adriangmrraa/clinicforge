#!/bin/bash
# ============================================
# PostgreSQL Backup Script — ClinicForge
# ============================================
#
# Usage:
#   ./scripts/backup_postgres.sh
#
# Environment variables:
#   POSTGRES_HOST     (default: localhost)
#   POSTGRES_PORT     (default: 5432)
#   POSTGRES_DB       (default: clinicforge)
#   POSTGRES_USER     (default: postgres)
#   POSTGRES_PASSWORD (required)
#   BACKUP_DIR        (default: /backups)
#   BACKUP_RETENTION  (default: 7 days)
#   S3_BACKUP_BUCKET  (optional — if set, uploads to S3)
#
# Cron example (daily at 3 AM):
#   0 3 * * * /app/scripts/backup_postgres.sh >> /var/log/backup.log 2>&1
#
# Restore:
#   pg_restore -h localhost -U postgres -d clinicforge -c backup_file.dump

set -euo pipefail

# Config
POSTGRES_HOST="${POSTGRES_HOST:-localhost}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"
POSTGRES_DB="${POSTGRES_DB:-clinicforge}"
POSTGRES_USER="${POSTGRES_USER:-postgres}"
BACKUP_DIR="${BACKUP_DIR:-/backups}"
BACKUP_RETENTION="${BACKUP_RETENTION:-7}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/clinicforge_backup_${TIMESTAMP}.dump"

echo "[$(date)] Starting backup of ${POSTGRES_DB}..."

# Ensure backup directory exists
mkdir -p "${BACKUP_DIR}"

# Run pg_dump
export PGPASSWORD="${POSTGRES_PASSWORD}"
if pg_dump \
    -h "${POSTGRES_HOST}" \
    -p "${POSTGRES_PORT}" \
    -U "${POSTGRES_USER}" \
    -d "${POSTGRES_DB}" \
    --format=custom \
    --file="${BACKUP_FILE}"; then

    FILE_SIZE=$(du -h "${BACKUP_FILE}" | cut -f1)
    echo "[$(date)] Backup completed: ${BACKUP_FILE} (${FILE_SIZE})"
else
    echo "[$(date)] ERROR: pg_dump failed"
    exit 1
fi

# Optional: Upload to S3
if [ -n "${S3_BACKUP_BUCKET:-}" ]; then
    echo "[$(date)] Uploading to s3://${S3_BACKUP_BUCKET}/clinicforge/..."
    if aws s3 cp "${BACKUP_FILE}" "s3://${S3_BACKUP_BUCKET}/clinicforge/$(basename ${BACKUP_FILE})"; then
        echo "[$(date)] Upload successful"
    else
        echo "[$(date)] WARNING: S3 upload failed — local backup preserved"
    fi
else
    echo "[$(date)] S3_BACKUP_BUCKET not set — skipping upload"
fi

# Retention: delete backups older than N days
echo "[$(date)] Cleaning backups older than ${BACKUP_RETENTION} days..."
find "${BACKUP_DIR}" -name "clinicforge_backup_*.dump" -mtime +"${BACKUP_RETENTION}" -delete 2>/dev/null || true

REMAINING=$(find "${BACKUP_DIR}" -name "clinicforge_backup_*.dump" | wc -l)
echo "[$(date)] Done. ${REMAINING} backup(s) retained."
