import httpx
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_admin, mutation_admin
from app.config import get_settings
from app.database import get_db
from app.models import Admin, EventLog

router = APIRouter(tags=["system"])

@router.get("/health")
async def health(db: AsyncSession = Depends(get_db)):
    await db.execute(text("SELECT 1")); return {"status": "ok"}

@router.get("/logs")
async def logs(db: AsyncSession = Depends(get_db), _: Admin = Depends(current_admin)):
    rows = (await db.execute(select(EventLog).order_by(EventLog.created_at.desc()).limit(100))).scalars().all()
    return [{"id": x.id, "type": x.event_type, "level": x.level, "message": x.message, "created_at": x.created_at} for x in rows]


@router.get("/browser/auth")
async def browser_auth(_: Admin = Depends(current_admin)):
    return Response(status_code=204)


async def browser_request(method: str, path: str) -> dict:
    settings = get_settings()
    if not settings.browser_manager_secret:
        raise HTTPException(503, "Przeglądarka VPS nie jest skonfigurowana")
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.request(method, f"{settings.browser_manager_url}{path}",
                headers={"X-Browser-Manager-Secret": settings.browser_manager_secret})
        response.raise_for_status(); return response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(503, "Kontener przeglądarki nie odpowiada") from exc


@router.get("/browser/status")
async def browser_status(_: Admin = Depends(current_admin)):
    return await browser_request("GET", "/status")


@router.post("/browser/{action}")
async def browser_control(action: str, db: AsyncSession = Depends(get_db), _: Admin = Depends(mutation_admin)):
    if action not in {"start", "stop", "restart"}:
        raise HTTPException(422, "Nieprawidłowa operacja")
    result = await browser_request("POST", f"/{action}")
    db.add(EventLog(event_type=f"browser_{action}", message=f"Chromium: wykonano operację {action}"))
    await db.commit()
    if action == "stop":
        try:
            from app.services.notifications import send_external
            await send_external("Przeglądarka VPS zatrzymana", "Chromium zostało ręcznie zatrzymane w panelu.")
        except Exception:
            pass
    return result
