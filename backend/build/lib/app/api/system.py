from fastapi import APIRouter, Depends
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_admin
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
