import logging
from contextlib import asynccontextmanager
from pathlib import Path

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI, Request
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, JSONResponse

from app.api import auth, campaigns, events, system, twitch_oauth
from app.config import get_settings
from app.services.scheduler import browser_sweep, channel_sweep, disk_sweep, notification_sweep, official_source_sweep

settings = get_settings()

@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler = AsyncIOScheduler(timezone="UTC")
    scheduler.add_job(notification_sweep, "interval", seconds=settings.sync_interval_seconds,
                      id="notification-sweep", max_instances=1, coalesce=True)
    scheduler.add_job(official_source_sweep, "interval", minutes=30,
                      id="official-source-sweep", max_instances=1, coalesce=True)
    scheduler.add_job(channel_sweep, "interval", minutes=5,
                      id="channel-sweep", max_instances=1, coalesce=True)
    scheduler.add_job(browser_sweep, "interval", minutes=1,
                      id="browser-sweep", max_instances=1, coalesce=True)
    scheduler.add_job(disk_sweep, "interval", minutes=10,
                      id="disk-sweep", max_instances=1, coalesce=True)
    scheduler.start()
    yield
    scheduler.shutdown(wait=False)

logger = logging.getLogger(__name__)

app = FastAPI(title="WoT Twitch Drops Dashboard", root_path=settings.base_path, lifespan=lifespan,
              docs_url="/api/docs" if settings.app_env != "production" else None)
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.include_router(system.router, prefix="/api")
app.include_router(auth.router, prefix="/api")
app.include_router(campaigns.router, prefix="/api")
app.include_router(twitch_oauth.router, prefix="/api")
app.include_router(events.router, prefix="/api")

@app.middleware("http")
async def security_headers(request: Request, call_next):
    try: response = await call_next(request)
    except Exception:
        logger.exception("Unhandled application error")
        return JSONResponse({"detail": "Wewnętrzny błąd aplikacji"}, status_code=500)
    response.headers.update({"X-Content-Type-Options": "nosniff", "X-Frame-Options": "SAMEORIGIN",
        "Referrer-Policy": "strict-origin-when-cross-origin", "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
        "Content-Security-Policy": "default-src 'self'; script-src 'self' https://embed.twitch.tv; frame-src https://player.twitch.tv https://www.twitch.tv; img-src 'self' data: https:; style-src 'self' 'unsafe-inline'; connect-src 'self'"})
    return response

dist = Path(__file__).parent / "static"
@app.get("/assets/{asset_path:path}", include_in_schema=False)
async def assets(asset_path: str):
    asset_root = (dist / "assets").resolve()
    target = (asset_root / asset_path).resolve()
    if asset_root not in target.parents or not target.is_file():
        from fastapi import HTTPException
        raise HTTPException(404, "Nie znaleziono pliku")
    return FileResponse(target)

@app.head("/{path:path}", include_in_schema=False)
async def spa_head(path: str):
    index = dist / "index.html"
    return FileResponse(index) if index.exists() else JSONResponse({}, 503)

@app.get("/{path:path}", include_in_schema=False)
async def spa(path: str):
    index = dist / "index.html"
    return FileResponse(index) if index.exists() else JSONResponse({"detail": "Frontend nie został zbudowany"}, 503)
