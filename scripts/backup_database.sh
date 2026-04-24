#!/usr/bin/env bash

set -euo pipefail

usage() {
  cat <<'USAGE'
Usage: scripts/backup_database.sh [--db PATH] [--out-dir DIR] [--prefix NAME]

Creates a timestamped backup of the active SQLite datastore.

Options:
  --db PATH        Path to SQLite database (default: config/pdsno.db)
  --out-dir DIR    Directory to store backups (default: backups)
  --prefix NAME    Backup file prefix (default: pdsno)
  -h, --help       Show this help message

Example:
  scripts/backup_database.sh --db config/pdsno.db --out-dir backups
USAGE
}

DB_PATH="config/pdsno.db"
OUT_DIR="backups"
PREFIX="pdsno"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --db)
      DB_PATH="$2"
      shift 2
      ;;
    --out-dir)
      OUT_DIR="$2"
      shift 2
      ;;
    --prefix)
      PREFIX="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown arg: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [[ "$DB_PATH" == postgresql://* ]]; then
  echo "PostgreSQL backups are not supported by this script yet." >&2
  exit 2
fi

if [[ ! -f "$DB_PATH" ]]; then
  echo "Database not found: $DB_PATH" >&2
  exit 1
fi

mkdir -p "$OUT_DIR"

STAMP=$(date +"%Y%m%d_%H%M%S")
DEST="$OUT_DIR/${PREFIX}_backup_${STAMP}.db"

if command -v sqlite3 >/dev/null 2>&1; then
  sqlite3 "$DB_PATH" ".backup '$DEST'"
else
  cp -p "$DB_PATH" "$DEST"
fi

echo "Backup created: $DEST"
