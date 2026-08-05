#!/usr/bin/env bash
set -euo pipefail
project_dir="${WOT_PROJECT_DIR:-/opt/wot-twitch-drops-dashboard}"
backup_dir="${WOT_BACKUP_DIR:-/var/backups/wot-twitch-drops-dashboard}"
cd "$project_dir"
install -d -m 700 "$backup_dir"
target="$backup_dir/wot-$(date -u +%Y%m%d-%H%M%S).dump"
umask 077
docker compose exec -T db pg_dump -U wot -d wot -Fc > "$target"
test -s "$target"
docker compose exec -T db pg_restore --list < "$target" >/dev/null
find "$backup_dir" -type f -name 'wot-*.dump' -mtime +14 -delete
printf '%s\n' "$target"
