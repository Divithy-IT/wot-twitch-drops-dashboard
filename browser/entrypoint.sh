#!/bin/sh
set -eu
profile=/home/browser/.mozilla/firefox/wot
for name in .parentlock lock; do
    target="$profile/$name"
    if [ -e "$target" ] || [ -L "$target" ]; then
        unlink "$target"
    fi
done
exec /usr/bin/supervisord -n -c /etc/supervisor/conf.d/browser.conf
