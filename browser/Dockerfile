FROM debian:bookworm-slim

RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates curl gnupg \
    && curl -fsSL https://dl.google.com/linux/linux_signing_key.pub \
       | gpg --dearmor -o /usr/share/keyrings/google-chrome.gpg \
    && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/google-chrome.gpg] https://dl.google.com/linux/chrome/deb/ stable main" \
       > /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update && apt-get install -y --no-install-recommends \
    google-chrome-stable dbus-x11 fonts-dejavu-core fonts-liberation novnc openbox \
    python3 supervisor websockify x11vnc xvfb \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 --shell /usr/sbin/nologin browser \
    && install -d -m 700 -o browser -g browser /home/browser/.config/chromium \
       "/home/browser/.config/google-chrome/Crash Reports" /run/browser

COPY --chown=browser:browser supervisord.conf /etc/supervisor/conf.d/browser.conf
COPY --chown=browser:browser manager.py /opt/browser/manager.py
COPY --chown=browser:browser --chmod=755 entrypoint.sh /opt/browser/entrypoint.sh

USER browser
ENV DISPLAY=:99 HOME=/home/browser
EXPOSE 6080 9000
HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD curl -fsS http://127.0.0.1:9000/health || exit 1
CMD ["/opt/browser/entrypoint.sh"]
