from app.api import system


async def authenticated(client):
    response = await client.post("/api/auth/setup", json={"username": "browseradmin", "password": "very-secure-password"})
    csrf = response.cookies["wot_csrf"]
    client.cookies.set("wot_session", response.cookies["wot_session"], path="/")
    client.cookies.set("wot_csrf", csrf, path="/")
    return {"X-CSRF-Token": csrf}


async def test_browser_requires_admin(client):
    assert (await client.get("/api/browser/status")).status_code == 401
    assert (await client.get("/api/browser/auth")).status_code == 401
    assert (await client.get("/api/browser/entry", follow_redirects=False)).status_code == 401


async def test_browser_status_and_csrf_control(client, monkeypatch):
    headers = await authenticated(client)

    async def fake_request(method, path):
        return {"container": "running", "chromium": "running", "novnc": "responding",
                "uptime_seconds": 10, "memory_bytes": 1234, "method": method, "path": path}

    monkeypatch.setattr(system, "browser_request", fake_request)
    entry = await client.get("/api/browser/entry", follow_redirects=False)
    assert entry.status_code == 302 and entry.headers["location"].startswith("/wot/browser/vnc.html")
    assert (await client.get("/api/browser/status")).json()["chromium"] == "running"
    assert (await client.post("/api/browser/restart")).status_code == 403
    response = await client.post("/api/browser/restart", headers=headers)
    assert response.status_code == 200 and response.json()["path"] == "/restart"
