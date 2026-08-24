#!/usr/bin/env bash
#
# Pull the database backups from the server to this machine (off-site copy).
#
# Why at all: the hourly backups sit on the same machine as the database. That
# protects against operator error and broken migrations — but not against
# losing or compromising the account. Only this second copy makes it a real
# backup.
#
# Usage:
#   deploy/pull-backups.sh                    # into ~/Backups/lma-connect
#   deploy/pull-backups.sh /path/to/target    # custom target directory
#
# Configure the source via environment variables (put them in your shell
# profile, they are deployment-specific and do not belong in the repo):
#   LMA_REMOTE_HOST   user@host of the server            (required)
#   LMA_REMOTE_DIR    backup dir on the server           (default: backups/lma-connect)
#   LMA_SSH_KEY       ssh key to use                     (default: ~/.ssh/id_ed25519)
#
# On the conference day, run it from cron every two hours as well:
#   0 9-19/2 * * * /path/to/repo/deploy/pull-backups.sh >> ~/Library/Logs/lma-backup-pull.log 2>&1

set -euo pipefail

REMOTE_HOST="${LMA_REMOTE_HOST:-}"
REMOTE_DIR="${LMA_REMOTE_DIR:-backups/lma-connect}"
SSH_KEY="${LMA_SSH_KEY:-$HOME/.ssh/id_ed25519}"
DEST="${1:-$HOME/Backups/lma-connect}"

if [[ -z "$REMOTE_HOST" ]]; then
    echo "ERROR: set LMA_REMOTE_HOST=user@host (the server holding the backups)" >&2
    exit 2
fi

mkdir -p "$DEST"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Pull $REMOTE_HOST:$REMOTE_DIR/ -> $DEST"

# --ignore-existing: backups are immutable, so never transfer a file twice.
# No --delete: we keep them locally for longer than the server does.
rsync -av --ignore-existing \
    -e "ssh -i $SSH_KEY -o ConnectTimeout=20 -o BatchMode=yes" \
    --include='db-*.sqlite3.gz' --include='media-*.tar.gz' --exclude='*' \
    "$REMOTE_HOST:$REMOTE_DIR/" "$DEST/"

newest="$(ls -1t "$DEST"/db-*.sqlite3.gz 2>/dev/null | head -1 || true)"
if [[ -z "$newest" ]]; then
    echo "ERROR: no backup in target directory $DEST" >&2
    exit 1
fi

# Verify that the file we pulled really is an intact SQLite database — an
# aborted transfer would otherwise only surface when it is actually needed.
tmp="$(mktemp -t lma-backup-verify)"
trap 'rm -f "$tmp"' EXIT
gunzip -c "$newest" > "$tmp"
result="$(sqlite3 "$tmp" 'PRAGMA integrity_check;')"
if [[ "$result" != "ok" ]]; then
    echo "ERROR: $newest is damaged — integrity_check: $result" >&2
    exit 1
fi

count="$(ls -1 "$DEST"/db-*.sqlite3.gz | wc -l | tr -d ' ')"
size="$(du -sh "$DEST" | cut -f1)"
echo "OK  $count backups locally ($size), newest: $(basename "$newest") — integrity_check ok"
