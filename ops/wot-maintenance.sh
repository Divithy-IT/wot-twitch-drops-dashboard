#!/bin/sh
set -eu

project=/opt/wot-twitch-drops-dashboard
backup_dir=/var/backups/wot-twitch-drops-dashboard
stamp=$(date -u +%Y%m%d-%H%M%S)
dump="$backup_dir/wot-$stamp.dump"

mkdir -p "$backup_dir"
cd "$project"
docker compose exec -T db pg_dump -U "${POSTGRES_USER:-wot}" -d "${POSTGRES_DB:-wot}" -Fc > "$dump"
test -s "$dump"
docker compose exec -T db pg_restore -l < "$dump" >/dev/null

# Keep exactly the five newest validated dashboard dumps.
find "$backup_dir" -maxdepth 1 -type f -name 'wot-*.dump' -printf '%T@ %p\n' \
  | sort -rn | awk 'NR > 5 {sub(/^[^ ]+ /, ""); print}' \
  | while IFS= read -r old; do test -n "$old" && find "$old" -maxdepth 0 -type f -delete; done

# Only dangling build cache older than seven days; never images, containers or volumes.
docker builder prune -f --filter until=168h

{
  date -u '+%Y-%m-%dT%H:%M:%SZ'
  df -h /
  du -xhd1 /root /var /opt 2>/dev/null | sort -h | tail -20
  docker system df
} > /var/log/wot-disk-maintenance.log
