FROM debian:bookworm-slim

RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates curl gnupg \
    && install -d -m 0755 /etc/apt/keyrings \
    && curl -fsSL https://packages.mozilla.org/apt/repo-signing-key.gpg \
       -o /etc/apt/keyrings/packages.mozilla.org.asc \
    && test "$(gpg --show-keys --with-colons /etc/apt/keyrings/packages.mozilla.org.asc | awk -F: '$1 == "fpr" {print $10; exit}')" \
       = "35BAA0B33E9EB396F59CA838C0BA5CE6DC6315A3" \
    && echo "deb [signed-by=/etc/apt/keyrings/packages.mozilla.org.asc] https://packages.mozilla.org/apt mozilla main" \
       > /etc/apt/sources.list.d/mozilla.list \
    && printf 'Package: *\nPin: origin packages.mozilla.org\nPin-Priority: 1000\n' \
       > /etc/apt/preferences.d/mozilla \
    && apt-get update && apt-get install -y --no-install-recommends \
    firefox firefox-l10n-pl dbus-x11 fonts-dejavu-core fonts-liberation novnc openbox \
    python3 supervisor websockify x11vnc xvfb \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 --shell /usr/sbin/nologin browser \
    && install -d -m 700 -o browser -g browser /home/browser/.mozilla/firefox/wot /run/browser

COPY --chown=browser:browser supervisord.conf /etc/supervisor/conf.d/browser.conf
COPY --chown=browser:browser manager.py /opt/browser/manager.py
COPY --chown=browser:browser --chmod=755 entrypoint.sh /opt/browser/entrypoint.sh
COPY --chown=browser:browser user.js /home/browser/.mozilla/firefox/wot/user.js

USER browser
ENV DISPLAY=:99 HOME=/home/browser
EXPOSE 6080 9000
HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD curl -fsS http://127.0.0.1:9000/health || exit 1
CMD ["/opt/browser/entrypoint.sh"]
