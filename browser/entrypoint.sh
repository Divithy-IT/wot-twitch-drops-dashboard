#!/bin/sh
set -eu
profile=/home/browser/.config/chromium
for name in SingletonCookie SingletonLock SingletonSocket; do
    target="$profile/$name"
    if [ -L "$target" ]; then
        unlink "$target"
    fi
done
exec /usr/bin/supervisord -n -c /etc/supervisor/conf.d/browser.conf
