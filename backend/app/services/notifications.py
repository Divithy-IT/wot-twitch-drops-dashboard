from email.message import EmailMessage

import aiosmtplib
import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import SessionLocal
from app.models import AppSetting, NotificationDelivery
from app.security import decrypt_token


async def reserve_delivery(db: AsyncSession, dedupe_key: str, channel: str) -> bool:
    existing = await db.scalar(select(NotificationDelivery).where(
        NotificationDelivery.dedupe_key == dedupe_key,
        NotificationDelivery.channel == channel,
    ))
    if existing: return False
    db.add(NotificationDelivery(dedupe_key=dedupe_key, channel=channel)); await db.commit(); return True


async def send_external(subject: str, body: str) -> None:
    settings = get_settings()
    webhook = settings.discord_webhook_url
    if not webhook:
        async with SessionLocal() as db:
            row = await db.get(AppSetting, "discord_webhook")
            if row and row.value.get("encrypted"):
                webhook = decrypt_token(row.value["encrypted"])
    if webhook:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(webhook, json={"content": f"**{subject}**\n{body}"})
            response.raise_for_status()
    if settings.smtp_host and settings.smtp_to and settings.smtp_from:
        message = EmailMessage(); message["From"] = settings.smtp_from; message["To"] = settings.smtp_to
        message["Subject"] = subject; message.set_content(body)
        await aiosmtplib.send(message, hostname=settings.smtp_host, port=settings.smtp_port,
            username=settings.smtp_username or None, password=settings.smtp_password or None, start_tls=True)
