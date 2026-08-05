import hmac
import json
import os
import subprocess
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

SECRET = os.environ.get("BROWSER_MANAGER_SECRET", "")
STARTED = time.monotonic()


def supervisor(action="status"):
    command = ["supervisorctl", "-c", "/etc/supervisor/conf.d/browser.conf"]
    command += [action, "chromium"] if action != "status" else ["status", "chromium"]
    result = subprocess.run(command, capture_output=True, text=True, timeout=25, check=False)
    return result.returncode, (result.stdout or result.stderr).strip()


def memory_bytes():
    try:
        with open("/sys/fs/cgroup/memory.current", encoding="ascii") as handle:
            return int(handle.read().strip())
    except (OSError, ValueError):
        return None


class Handler(BaseHTTPRequestHandler):
    def log_message(self, _format, *_args):
        return

    def reply(self, status, body):
        payload = json.dumps(body).encode()
        self.send_response(status); self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload))); self.end_headers(); self.wfile.write(payload)

    def authenticated(self):
        supplied = self.headers.get("X-Browser-Manager-Secret", "")
        return bool(SECRET) and hmac.compare_digest(supplied, SECRET)

    def do_GET(self):
        if self.path == "/health":
            return self.reply(200, {"status": "ok"})
        if self.path != "/status" or not self.authenticated():
            return self.reply(401, {"detail": "unauthorized"})
        code, output = supervisor()
        running = code == 0 and "RUNNING" in output
        self.reply(200, {"container": "running", "chromium": "running" if running else "stopped",
                         "novnc": "responding", "uptime_seconds": int(time.monotonic() - STARTED),
                         "memory_bytes": memory_bytes()})

    def do_POST(self):
        if not self.authenticated() or self.path not in {"/start", "/stop", "/restart"}:
            return self.reply(401, {"detail": "unauthorized"})
        action = self.path[1:]
        code, output = supervisor(action)
        self.reply(200 if code == 0 else 409, {"ok": code == 0, "state": output[-200:]})


ThreadingHTTPServer(("0.0.0.0", 9000), Handler).serve_forever()
