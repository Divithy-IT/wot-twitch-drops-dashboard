from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Admin
from app.security import read_session, require_csrf


async def current_admin(request: Request, db: AsyncSession = Depends(get_db)) -> Admin:
    data = read_session(request)
    admin = await db.get(Admin, data["admin_id"])
    if not admin or admin.session_version != data["version"]:
        from fastapi import HTTPException
        raise HTTPException(401, "Sesja jest nieważna")
    return admin


async def mutation_admin(request: Request, admin: Admin = Depends(current_admin)) -> Admin:
    require_csrf(request)
    return admin
