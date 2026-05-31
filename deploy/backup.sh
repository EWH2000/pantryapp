#!/usr/bin/env bash
# Consistent snapshot of the pantryapp SQLite database to a host-owned
# folder. Uses SQLite's online backup API (safe to run while the app is
# writing — no need to stop the container). Keeps the newest $KEEP snapshots.
#
# Run manually:           deploy/backup.sh
# Run daily via systemd:  pantryapp-backup.timer (see deploy/)
set -euo pipefail

CONTAINER="${PANTRY_CONTAINER:-pantryapp}"
BACKUP_DIR="${PANTRY_BACKUP_DIR:-$HOME/.local/share/pantryapp/backups}"
KEEP="${PANTRY_BACKUP_KEEP:-14}"

mkdir -p "$BACKUP_DIR"
ts="$(date +%Y%m%d-%H%M%S)"
dest="$BACKUP_DIR/pantry-$ts.db"

# 1) Consistent snapshot inside the volume via SQLite online backup.
podman exec "$CONTAINER" python -c \
    "import sqlite3; s=sqlite3.connect('/data/pantry.db'); d=sqlite3.connect('/data/.snapshot.db'); s.backup(d); d.close(); s.close()"

# 2) Copy it out to the host — podman cp writes as the host user, so the
#    snapshot is owned by you and easy to copy offsite.
podman cp "$CONTAINER:/data/.snapshot.db" "$dest"

# 3) Drop the in-volume temp copy.
podman exec "$CONTAINER" rm -f /data/.snapshot.db

# 4) Prune to the newest $KEEP snapshots.
ls -1t "$BACKUP_DIR"/pantry-*.db 2>/dev/null | tail -n +"$((KEEP + 1))" | xargs -r rm -f || true

echo "backup written: $dest"
