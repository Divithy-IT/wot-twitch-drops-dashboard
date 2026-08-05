from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api import auth, campaigns, system, twitch_oauth
from app.config import get_settings

settings = get_settings()

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield

app = FastAPI(title="WoT Twitch Drops Dashboard", root_path=settings.base_path, lifespan=lifespan,
              docs_url="/api/docs" if settings.app_env != "production" else None)
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.include_router(system.router, prefix="/api")
app.include_router(auth.router, prefix="/api")
app.include_router(campaigns.router, prefix="/api")
app.include_router(twitch_oauth.router, prefix="/api")

@app.middleware("http")
async def security_headers(request: Request, call_next):
    try: response = await call_next(request)
    except Exception:
        return JSONResponse({"detail": "Wewnętrzny błąd aplikacji"}, status_code=500)
    response.headers.update({"X-Content-Type-Options": "nosniff", "X-Frame-Options": "SAMEORIGIN",
        "Referrer-Policy": "strict-origin-when-cross-origin", "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
        "Content-Security-Policy": "default-src 'self'; script-src 'self' https://embed.twitch.tv; frame-src https://player.twitch.tv https://www.twitch.tv; img-src 'self' data: https:; style-src 'self' 'unsafe-inline'; connect-src 'self'"})
    return response

dist = Path(__file__).parent / "static"
if dist.exists():
    app.mount("/assets", StaticFiles(directory=dist / "assets", check_dir=False), name="assets")

@app.get("/{path:path}", include_in_schema=False)
async def spa(path: str):
    index = dist / "index.html"
    return FileResponse(index) if index.exists() else JSONResponse({"detail": "Frontend nie został zbudowany"}, 503)
