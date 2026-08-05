from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import NotificationDelivery


async def reserve_delivery(db: AsyncSession, dedupe_key: str, channel: str) -> bool:
    existing = await db.scalar(select(NotificationDelivery).where(
        NotificationDelivery.dedupe_key == dedupe_key,
        NotificationDelivery.channel == channel,
    ))
    if existing:
        return False
    db.add(NotificationDelivery(dedupe_key=dedupe_key, channel=channel))
    await db.commit()
    return True
