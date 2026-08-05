FROM debian:bookworm-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    chromium chromium-sandbox dbus-x11 fonts-dejavu-core fonts-liberation novnc openbox \
    python3 supervisor websockify x11vnc xvfb ca-certificates curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 --shell /usr/sbin/nologin browser \
    && install -d -o browser -g browser /home/browser/.config/chromium /run/browser

COPY --chown=browser:browser supervisord.conf /etc/supervisor/conf.d/browser.conf
COPY --chown=browser:browser manager.py /opt/browser/manager.py

USER browser
ENV DISPLAY=:99 HOME=/home/browser
EXPOSE 6080 9000
HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD curl -fsS http://127.0.0.1:9000/health || exit 1
CMD ["/usr/bin/supervisord", "-n", "-c", "/etc/supervisor/conf.d/browser.conf"]
