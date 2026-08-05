from app.database import SessionLocal
from app.services.notifications import reserve_delivery


async def test_deduplication():
 async with SessionLocal() as db:
  assert await reserve_delivery(db,'campaign:1:start','in_app') is True
  assert await reserve_delivery(db,'campaign:1:start','in_app') is False
