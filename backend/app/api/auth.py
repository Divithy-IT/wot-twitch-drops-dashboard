from collections import defaultdict, deque
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_admin, mutation_admin
from app.config import get_settings
from app.database import get_db
from app.models import Admin, EventLog
from app.security import csrf_token, hash_password, make_session, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])
attempts: dict[str, deque[datetime]] = defaultdict(deque)


class Credentials(BaseModel):
    username: str = Field(min_length=3, max_length=80)
    password: str = Field(min_length=12, max_length=200)


def set_cookies(response: Response, admin: Admin, csrf: str) -> None:
    secure = get_settings().secure_cookies
    path = get_settings().base_path or "/"
    response.set_cookie("wot_session", make_session(admin.id, admin.session_version), httponly=True,
                        secure=secure, samesite="lax", path=path, max_age=get_settings().session_hours * 3600)
    response.set_cookie("wot_csrf", csrf, httponly=False, secure=secure, samesite="strict", path=path)


@router.get("/state")
async def state(request: Request, db: AsyncSession = Depends(get_db)):
    count = await db.scalar(select(func.count()).select_from(Admin))
    try:
        admin = await current_admin(request, db)
        return {"authenticated": True, "setup_required": False, "username": admin.username,
                "csrf_token": csrf_token(request)}
    except HTTPException:
        return {"authenticated": False, "setup_required": count == 0}


@router.post("/setup", status_code=201)
async def setup(data: Credentials, request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    if await db.scalar(select(func.count()).select_from(Admin)):
        raise HTTPException(409, "Administrator już istnieje")
    admin = Admin(username=data.username, password_hash=hash_password(data.password))
    db.add(admin)
    await db.flush()
    db.add(EventLog(event_type="admin_created", message="Utworzono pierwszego administratora"))
    await db.commit()
    set_cookies(response, admin, csrf_token(request))
    return {"ok": True}


@router.post("/login")
async def login(data: Credentials, request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    key = request.client.host if request.client else "unknown"
    now = datetime.now(UTC)
    while attempts[key] and attempts[key][0] < now - timedelta(minutes=15): attempts[key].popleft()
    if len(attempts[key]) >= 5: raise HTTPException(429, "Zbyt wiele prób. Spróbuj później")
    admin = await db.scalar(select(Admin).where(Admin.username == data.username))
    if not admin or not verify_password(admin.password_hash, data.password):
        attempts[key].append(now)
        raise HTTPException(401, "Nieprawidłowe dane logowania")
    attempts[key].clear()
    set_cookies(response, admin, csrf_token(request))
    return {"ok": True}


@router.post("/logout")
async def logout(response: Response, _: Admin = Depends(mutation_admin)):
    response.delete_cookie("wot_session", path=get_settings().base_path or "/")
    return {"ok": True}


@router.post("/sessions/revoke")
async def revoke(response: Response, admin: Admin = Depends(mutation_admin), db: AsyncSession = Depends(get_db)):
    admin.session_version += 1
    await db.commit()
    response.delete_cookie("wot_session", path=get_settings().base_path or "/")
    return {"ok": True}


@router.post("/password")
async def password(data: Credentials, admin: Admin = Depends(mutation_admin), db: AsyncSession = Depends(get_db)):
    admin.password_hash = hash_password(data.password)
    admin.session_version += 1
    await db.commit()
    return {"ok": True}
