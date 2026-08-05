from datetime import UTC, datetime
from email.message import EmailMessage

import aiosmtplib
import httpx
from sqlalchemy import select

from app.config import get_settings
from app.database import SessionLocal
from app.models import Campaign, EventLog
from app.services.notifications import reserve_delivery

WINDOWS = {
    "start_24h": ("starts_at", 24 * 3600, "Kampania rozpocznie się za 24 godziny"),
    "start_1h": ("starts_at", 3600, "Kampania rozpocznie się za godzinę"),
    "start": ("starts_at", 0, "Kampania właśnie się rozpoczęła"),
    "end_2h": ("ends_at", 2 * 3600, "Kampania zakończy się za dwie godziny"),
}


async def send_external(subject: str, body: str) -> None:
    settings = get_settings()
    if settings.discord_webhook_url:
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(settings.discord_webhook_url, json={"content": f"**{subject}**\n{body}"})
    if settings.smtp_host and settings.smtp_to and settings.smtp_from:
        message = EmailMessage()
        message["From"] = settings.smtp_from
        message["To"] = settings.smtp_to
        message["Subject"] = subject
        message.set_content(body)
        await aiosmtplib.send(
            message,
            hostname=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_username or None,
            password=settings.smtp_password or None,
            start_tls=True,
        )


async def notification_sweep() -> None:
    now = datetime.now(UTC)
    enabled = set(get_settings().notification_types.split(","))
    async with SessionLocal() as db:
        campaigns = (await db.execute(select(Campaign))).scalars().all()
        for campaign in campaigns:
            for kind, (field, offset, message) in WINDOWS.items():
                if kind not in enabled:
                    continue
                target = getattr(campaign, field)
                if target.tzinfo is None:
                    target = target.replace(tzinfo=UTC)
                delta = (target - now).total_seconds() - offset
                if -60 < delta <= 60:
                    key = f"campaign:{campaign.id}:{kind}"
                    if await reserve_delivery(db, key, "in_app"):
                        subject = f"{message}: {campaign.title}"
                        db.add(EventLog(event_type=f"notification_{kind}", message=subject))
                        await db.commit()
                        try:
                            await send_external(subject, campaign.link_url)
                        except Exception:
                            db.add(EventLog(event_type="notification_error", level="error", message="Nie udało się wysłać powiadomienia zewnętrznego"))
                            await db.commit()
