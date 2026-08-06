import shutil
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.config import get_settings
from app.database import SessionLocal
from app.models import (
    AppSetting,
    Campaign,
    DecisionHistory,
    DetectedEvent,
    EventLog,
    QualificationDecision,
    TwitchConnection,
    WatchedChannel,
)
from app.security import decrypt_token
from app.services.freshness import ACTIVE_FRESHNESS, assess_freshness
from app.services.notifications import reserve_delivery, send_external
from app.services.official_sources import sync_official_sources
from app.services.qualification import apply_qualification
from app.services.twitch import TwitchClient

WINDOWS = {"start_24h": ("starts_at", 86400, "Kampania rozpocznie się za 24 godziny"),
    "start_1h": ("starts_at", 3600, "Kampania rozpocznie się za godzinę"),
    "start": ("starts_at", 0, "Kampania właśnie się rozpoczęła"),
    "end_2h": ("ends_at", 7200, "Kampania zakończy się za dwie godziny")}


async def notification_sweep() -> None:
    now = datetime.now(UTC); enabled = set(get_settings().notification_types.split(","))
    async with SessionLocal() as db:
        for campaign in (await db.execute(select(Campaign).where(
            Campaign.archived.is_(False), Campaign.freshness_status.in_(ACTIVE_FRESHNESS)
        ))).scalars().all():
            for kind, (field, offset, message) in WINDOWS.items():
                if kind not in enabled: continue
                target = getattr(campaign, field)
                if target is None: continue
                if target.tzinfo is None: target = target.replace(tzinfo=UTC)
                if -60 < (target - now).total_seconds() - offset <= 60:
                    key = f"campaign:{campaign.id}:{kind}"
                    if await reserve_delivery(db, key, "in_app"):
                        subject = f"{message}: {campaign.title}"
                        db.add(EventLog(event_type=f"notification_{kind}", message=subject)); await db.commit()
                        try: await send_external(subject, campaign.link_url)
                        except Exception:
                            db.add(EventLog(event_type="notification_error", level="error", message="Nie udało się wysłać powiadomienia zewnętrznego")); await db.commit()
        if now.hour == 18 and now.minute <= 1:
            key = f"drops-inventory-reminder:{now.date().isoformat()}"
            if await reserve_delivery(db, key, "in_app"):
                message = "Przypomnienie: ręcznie sprawdź Twitch Drops Inventory"
                db.add(EventLog(event_type="drops_inventory_reminder", message=message)); await db.commit()
                try: await send_external("Twitch Drops Inventory", message)
                except Exception: pass


async def official_source_sweep() -> None:
    async with SessionLocal() as db:
        now = datetime.now(UTC)
        state = await db.get(AppSetting, "official_source_schedule")
        last = datetime.fromisoformat(state.value["last_run"]) if state and state.value.get("last_run") else None
        candidates = (await db.execute(select(DetectedEvent).where(
            DetectedEvent.qualification_decision == QualificationDecision.manual_review,
            DetectedEvent.freshness_status.in_(ACTIVE_FRESHNESS)
        ))).scalars().all()
        archive_setting = await db.get(AppSetting, "auto_archive_ended")
        if archive_setting is None or archive_setting.value.get("enabled", True):
            all_events = (await db.execute(select(DetectedEvent))).scalars().all()
            for item in all_events:
                fresh = assess_freshness(item, now)
                if fresh.status in {"historical", "reference_document"} and item.freshness_status != fresh.status:
                    await apply_qualification(db, item)
            await db.commit()
        interval = timedelta(hours=6)
        if any(x.starts_at and now <= (x.starts_at.replace(tzinfo=UTC) if x.starts_at.tzinfo is None else x.starts_at) <= now + timedelta(hours=24) for x in candidates):
            interval = timedelta(minutes=30)
        elif candidates:
            interval = timedelta(hours=1)
        if last and now - last < interval: return
        result = await sync_official_sources(db)
        if not state: state = AppSetting(key="official_source_schedule", value={}); db.add(state)
        state.value = {"last_run": now.isoformat(), "interval_minutes": int(interval.total_seconds() / 60)}
        await db.commit()
        if result.get("created"):
            try: await send_external("Nowe oficjalne informacje WoT", f"Wykryto propozycje: {result['created']}")
            except Exception: pass
        recent = (await db.execute(select(DecisionHistory).where(
            DecisionHistory.created_at >= now - timedelta(minutes=10)
        ))).scalars().all()
        for decision in recent:
            key = f"qualification:{decision.id}"
            if not await reserve_delivery(db, key, "external"): continue
            item = await db.get(DetectedEvent, decision.detected_event_id)
            if not item: continue
            if item.freshness_status not in ACTIVE_FRESHNESS: continue
            if decision.decision == QualificationDecision.auto_approve:
                subject = "Automatycznie zatwierdzono kampanię Twitch Drops"
            elif decision.decision == QualificationDecision.manual_review:
                subject = "Kampania Twitch Drops wymaga ręcznej decyzji"
            else:
                continue
            if decision.reward_value.value == "high": subject = "Wykryto Drops wysokiej wartości"
            try: await send_external(subject, f"{item.title}. Wartość: {decision.reward_value.value}. Pewność: {decision.score}/100.")
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


async def browser_sweep() -> None:
    """Monitor processes only; never inspect browser pages, cookies or its profile."""
    from app.api.system import browser_request
    from app.models import AppSetting
    try:
        status = await browser_request("GET", "/status")
    except Exception:
        status = {"browser": "unavailable"}
    async with SessionLocal() as db:
        state = status.get("browser", "unavailable")
        setting = await db.get(AppSetting, "browser_monitor_state")
        previous = setting.value.get("state", "unknown") if setting else "unknown"
        if state != "running" and previous == "running":
            db.add(EventLog(event_type="browser_crashed", level="error",
                            message="Firefox zakończył działanie — wymagany ręczny restart"))
            try: await send_external("Przeglądarka VPS", "Firefox zakończył działanie. Uruchom go ręcznie w panelu.")
            except Exception: pass
        if not setting:
            setting = AppSetting(key="browser_monitor_state", value={"state": state}); db.add(setting)
        else: setting.value = {"state": state}
        await db.commit()


async def disk_sweep() -> None:
    """Alert at 80/85/90 percent without deleting anything."""
    total, used, free = shutil.disk_usage("/")
    percent = used * 100 / total
    threshold = 90 if percent >= 90 else 85 if percent >= 85 else 80 if percent >= 80 else 0
    if not threshold: return
    now = datetime.now(UTC)
    async with SessionLocal() as db:
        key = f"disk:{threshold}:{now.date().isoformat()}"
        if not await reserve_delivery(db, key, "in_app"): return
        message = f"Dysk VPS wykorzystany w {percent:.1f}% — wolne {free / 1024**3:.1f} GiB."
        db.add(EventLog(event_type="disk_usage_alert", level="error" if threshold >= 90 else "warning",
                        message=message, details={"percent": round(percent, 1), "threshold": threshold}))
        await db.commit()
        try: await send_external(f"Alert dysku VPS: próg {threshold}%", message)
        except Exception: pass
