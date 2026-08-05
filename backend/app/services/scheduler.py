from datetime import UTC, datetime

from sqlalchemy import select

from app.config import get_settings
from app.database import SessionLocal
from app.models import Campaign, EventLog, TwitchConnection, WatchedChannel
from app.security import decrypt_token
from app.services.notifications import reserve_delivery, send_external
from app.services.official_sources import sync_official_sources
from app.services.twitch import TwitchClient

WINDOWS = {"start_24h": ("starts_at", 86400, "Kampania rozpocznie się za 24 godziny"),
    "start_1h": ("starts_at", 3600, "Kampania rozpocznie się za godzinę"),
    "start": ("starts_at", 0, "Kampania właśnie się rozpoczęła"),
    "end_2h": ("ends_at", 7200, "Kampania zakończy się za dwie godziny")}


async def notification_sweep() -> None:
    now = datetime.now(UTC); enabled = set(get_settings().notification_types.split(","))
    async with SessionLocal() as db:
        for campaign in (await db.execute(select(Campaign))).scalars().all():
            for kind, (field, offset, message) in WINDOWS.items():
                if kind not in enabled: continue
                target = getattr(campaign, field)
                if target.tzinfo is None: target = target.replace(tzinfo=UTC)
                if -60 < (target - now).total_seconds() - offset <= 60:
                    key = f"campaign:{campaign.id}:{kind}"
                    if await reserve_delivery(db, key, "in_app"):
                        subject = f"{message}: {campaign.title}"
                        db.add(EventLog(event_type=f"notification_{kind}", message=subject)); await db.commit()
                        try: await send_external(subject, campaign.link_url)
                        except Exception:
                            db.add(EventLog(event_type="notification_error", level="error", message="Nie udało się wysłać powiadomienia zewnętrznego")); await db.commit()


async def official_source_sweep() -> None:
    async with SessionLocal() as db:
        result = await sync_official_sources(db)
        if result.get("created"):
            try: await send_external("Nowe oficjalne informacje WoT", f"Wykryto propozycje: {result['created']}")
            except Exception: pass


async def channel_sweep() -> None:
    async with SessionLocal() as db:
        conn = await db.scalar(select(TwitchConnection))
        if not conn: return
        client = TwitchClient(); token = decrypt_token(conn.access_token_encrypted)
        for channel in (await db.execute(select(WatchedChannel))).scalars().all():
            try: stream = await client.stream(token, channel.login)
            except Exception: continue
            if not stream: continue
            key = f"stream:{channel.login}:{stream['started_at']}"
            if await reserve_delivery(db, key, "in_app"):
                message = f"Kanał {channel.login} rozpoczął transmisję: {stream['title']}"
                db.add(EventLog(event_type="watched_stream_started", message=message,
                    details={"channel": channel.login, "started_at": stream["started_at"]})); await db.commit()
                try: await send_external("Rozpoczęła się transmisja WoT", message)
                except Exception: pass
