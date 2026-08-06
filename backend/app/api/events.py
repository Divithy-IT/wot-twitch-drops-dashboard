from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, HttpUrl
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_admin, mutation_admin
from app.database import get_db
from app.models import (
    Admin,
    AppSetting,
    Campaign,
    Confidence,
    DecisionHistory,
    DetectedEvent,
    DetectionStatus,
    EventLog,
    ProgressSource,
    QualificationDecision,
    Reward,
    SourceType,
    TrustedSource,
    WatchedChannel,
)
from app.security import encrypt_token
from app.services.freshness import ACTIVE_FRESHNESS
from app.services.notifications import send_external
from app.services.official_sources import reanalyze_detected_event, sync_official_sources
from app.services.qualification import DEFAULT_RULES, apply_qualification

router = APIRouter(tags=["events"])


class DetectionEdit(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    summary: str = Field(default="", max_length=5000)
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    stream_times: list[str] = Field(default_factory=list)
    probable_rewards: list[str] = Field(default_factory=list)
    required_minutes: int | None = Field(default=None, ge=0, le=10000)
    event_type: str = Field(default="event", max_length=50)
    confidence: Confidence = Confidence.low


class Approval(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=5000)
    starts_at: datetime
    ends_at: datetime
    required_minutes: int = Field(default=0, ge=0, le=10000)
    eligible_channels: list[str] = Field(default_factory=list)
    rewards: list[str] = Field(default_factory=list)
    link_url: HttpUrl


def detection_json(item: DetectedEvent) -> dict:
    return {"id": item.id, "title": item.title, "summary": item.summary,
        "published_at": item.published_at, "starts_at": item.starts_at, "ends_at": item.ends_at,
        "stream_times": item.stream_times, "probable_rewards": item.probable_rewards,
        "required_minutes": item.required_minutes, "source_url": item.source_url,
        "source_name": item.source_name, "last_checked_at": item.last_checked_at,
        "excerpt": item.excerpt, "confidence": item.confidence, "event_type": item.event_type,
        "status": item.status, "approved_campaign_id": item.approved_campaign_id,
        "qualification_decision": item.qualification_decision, "confidence_score": item.confidence_score,
        "reward_value": item.reward_value, "matched_keywords": item.matched_keywords,
        "score_breakdown": item.score_breakdown, "decision_reason": item.decision_reason,
        "decided_by": item.decided_by, "decided_at": item.decided_at,
        "source_verified_at": item.source_verified_at, "freshness_status": item.freshness_status,
        "detected_date_text": item.detected_date_text, "date_confidence": item.date_confidence}


@router.get("/detected-events")
async def detections(status: DetectionStatus | None = None, db: AsyncSession = Depends(get_db), _: Admin = Depends(current_admin)):
    query = select(DetectedEvent).order_by(DetectedEvent.published_at.desc().nullslast())
    if status: query = query.where(DetectedEvent.status == status)
    return [detection_json(x) for x in (await db.execute(query.limit(200))).scalars().all()]


@router.put("/detected-events/{event_id}")
async def edit_detection(event_id: int, data: DetectionEdit, db: AsyncSession = Depends(get_db), _: Admin = Depends(mutation_admin)):
    item = await db.get(DetectedEvent, event_id)
    if not item: raise HTTPException(404, "Nie znaleziono propozycji")
    for key, value in data.model_dump().items(): setattr(item, key, value)
    await db.commit(); return {"ok": True}


@router.post("/detected-events/{event_id}/approve")
async def approve(event_id: int, data: Approval, db: AsyncSession = Depends(get_db), _: Admin = Depends(mutation_admin)):
    item = await db.get(DetectedEvent, event_id)
    if not item: raise HTTPException(404, "Nie znaleziono propozycji")
    if item.status == DetectionStatus.approved: raise HTTPException(409, "Propozycja jest już zatwierdzona")
    if data.ends_at <= data.starts_at: raise HTTPException(422, "Koniec musi przypadać po rozpoczęciu")
    campaign = Campaign(title=data.title, description=data.description, starts_at=data.starts_at,
        ends_at=data.ends_at, required_minutes=data.required_minutes,
        eligible_channels=data.eligible_channels, link_url=str(data.link_url),
        source_type=SourceType.wargaming, source_url=item.source_url,
        source_updated_at=datetime.now(UTC), progress_source=ProgressSource.manual)
    campaign.rewards = [Reward(name=name, required_minutes=data.required_minutes) for name in data.rewards]
    db.add(campaign); await db.flush(); item.status = DetectionStatus.approved; item.approved_campaign_id = campaign.id
    item.qualification_decision = QualificationDecision.auto_approve
    item.decided_by = "administrator"; item.decided_at = datetime.now(UTC)
    db.add(DecisionHistory(detected_event_id=item.id, decision=QualificationDecision.auto_approve,
        score=item.confidence_score, reward_value=item.reward_value, reason="Ręczne zatwierdzenie administratora",
        score_breakdown=item.score_breakdown, matched_keywords=item.matched_keywords,
        actor="administrator", action="manual_approve"))
    db.add(EventLog(event_type="detected_event_approved", message=f"Zatwierdzono propozycję: {item.title}"))
    await db.commit(); return {"campaign_id": campaign.id}


@router.post("/detected-events/{event_id}/reanalyze")
async def reanalyze(event_id: int, db: AsyncSession = Depends(get_db), _: Admin = Depends(mutation_admin)):
    item = await db.get(DetectedEvent, event_id)
    if not item: raise HTTPException(404, "Nie znaleziono propozycji")
    try:
        return detection_json(await reanalyze_detected_event(db, item))
    except Exception as exc:
        await db.rollback()
        raise HTTPException(502, "Oficjalne źródło jest chwilowo niedostępne") from exc


@router.post("/detected-events/{event_id}/undo")
async def undo_decision(event_id: int, db: AsyncSession = Depends(get_db), _: Admin = Depends(mutation_admin)):
    item = await db.get(DetectedEvent, event_id)
    if not item: raise HTTPException(404, "Nie znaleziono propozycji")
    if item.approved_campaign_id:
        campaign = await db.get(Campaign, item.approved_campaign_id)
        if campaign and campaign.auto_approved: await db.delete(campaign)
        elif campaign: raise HTTPException(409, "Ręcznie utworzonej kampanii nie można cofnąć tym przyciskiem")
    item.status = DetectionStatus.pending; item.approved_campaign_id = None
    item.qualification_decision = QualificationDecision.manual_review
    item.decision_reason = "Decyzja cofnięta przez administratora"; item.decided_by = "administrator"
    db.add(DecisionHistory(detected_event_id=item.id, decision=QualificationDecision.manual_review,
        score=item.confidence_score, reward_value=item.reward_value, reason=item.decision_reason,
        score_breakdown=item.score_breakdown, matched_keywords=item.matched_keywords,
        actor="administrator", action="undo"))
    await db.commit(); return {"ok": True}


@router.post("/detected-events/{event_id}/qualify")
async def qualify_again(event_id: int, db: AsyncSession = Depends(get_db), _: Admin = Depends(mutation_admin)):
    item = await db.get(DetectedEvent, event_id)
    if not item: raise HTTPException(404, "Nie znaleziono propozycji")
    result = await apply_qualification(db, item, "administrator")
    await db.commit(); return {"decision": result.decision, "score": result.score}


@router.post("/detected-events/bulk/ignore-streams")
async def ignore_plain_streams(db: AsyncSession = Depends(get_db), _: Admin = Depends(mutation_admin)):
    rows = (await db.execute(select(DetectedEvent).where(DetectedEvent.status == DetectionStatus.pending))).scalars().all()
    ignored = 0
    drops_phrases = ("twitch drops", "drops enabled", "drops inventory", "odbierz drop", "nagrody za oglądanie")
    for item in rows:
        text = f"{item.title} {item.summary} {item.excerpt}".lower()
        plain_stream = item.event_type == "stream" or any(x in text for x in ("stream", "transmis", " live "))
        if not plain_stream or any(x in text for x in drops_phrases): continue
        item.status = DetectionStatus.rejected; item.qualification_decision = QualificationDecision.auto_ignore
        item.decision_reason = "Zbiorczo zignorowano transmisję bez literalnej wzmianki o Twitch Drops"
        item.decided_by = "administrator"; item.decided_at = datetime.now(UTC); ignored += 1
        db.add(DecisionHistory(detected_event_id=item.id, decision=QualificationDecision.auto_ignore,
            score=item.confidence_score, reward_value=item.reward_value, reason=item.decision_reason,
            score_breakdown=item.score_breakdown, matched_keywords=item.matched_keywords,
            actor="administrator", action="bulk_ignore_plain_stream"))
    await db.commit(); return {"ignored": ignored}


@router.post("/detected-events/bulk/archive-past")
async def archive_past(db: AsyncSession = Depends(get_db), _: Admin = Depends(mutation_admin)):
    rows = (await db.execute(select(DetectedEvent).where(
        DetectedEvent.freshness_status.in_(["historical", "reference_document"])
    ))).scalars().all()
    changed = 0
    for item in rows:
        if item.status == DetectionStatus.pending or item.qualification_decision != QualificationDecision.auto_ignore:
            changed += 1
        await apply_qualification(db, item, "administrator")
    await db.commit()
    return {"archived": changed}


@router.post("/detected-events/{event_id}/{decision}")
async def decide(event_id: int, decision: str, db: AsyncSession = Depends(get_db), _: Admin = Depends(mutation_admin)):
    if decision not in {"reject", "duplicate"}: raise HTTPException(422, "Nieprawidłowa decyzja")
    item = await db.get(DetectedEvent, event_id)
    if not item: raise HTTPException(404, "Nie znaleziono propozycji")
    item.status = DetectionStatus.rejected if decision == "reject" else DetectionStatus.duplicate
    item.qualification_decision = QualificationDecision.auto_ignore
    item.decision_reason = "Odrzucono ręcznie" if decision == "reject" else "Oznaczono jako duplikat"
    item.decided_by = "administrator"; item.decided_at = datetime.now(UTC)
    db.add(DecisionHistory(detected_event_id=item.id, decision=QualificationDecision.auto_ignore,
        score=item.confidence_score, reward_value=item.reward_value, reason=item.decision_reason,
        score_breakdown=item.score_breakdown, matched_keywords=item.matched_keywords,
        actor="administrator", action=decision))
    db.add(EventLog(event_type=f"detected_event_{decision}", message=f"Zmieniono propozycję: {item.title}"))
    await db.commit(); return {"ok": True}


class TrustedSourceIn(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    url_pattern: HttpUrl
    enabled: bool = True
    auto_approve: bool = True
    max_trust_score: int = Field(default=100, ge=0, le=100)
    ignored: bool = False


@router.get("/trusted-sources")
async def trusted_sources(db: AsyncSession = Depends(get_db), _: Admin = Depends(current_admin)):
    rows = (await db.execute(select(TrustedSource).order_by(TrustedSource.name))).scalars().all()
    return [{"id": x.id, "name": x.name, "url_pattern": x.url_pattern, "enabled": x.enabled,
             "auto_approve": x.auto_approve, "max_trust_score": x.max_trust_score, "ignored": x.ignored} for x in rows]


@router.post("/trusted-sources", status_code=201)
async def add_trusted_source(data: TrustedSourceIn, db: AsyncSession = Depends(get_db), _: Admin = Depends(mutation_admin)):
    url = str(data.url_pattern)
    if await db.scalar(select(TrustedSource).where(TrustedSource.url_pattern == url)): raise HTTPException(409, "Źródło już istnieje")
    db.add(TrustedSource(**data.model_dump(exclude={"url_pattern"}), url_pattern=url)); await db.commit(); return {"ok": True}


@router.put("/trusted-sources/{source_id}")
async def update_trusted_source(source_id: int, data: TrustedSourceIn, db: AsyncSession = Depends(get_db), _: Admin = Depends(mutation_admin)):
    row = await db.get(TrustedSource, source_id)
    if not row: raise HTTPException(404, "Nie znaleziono źródła")
    for key, value in data.model_dump().items(): setattr(row, key, str(value) if key == "url_pattern" else value)
    await db.commit(); return {"ok": True}


@router.delete("/trusted-sources/{source_id}")
async def delete_trusted_source(source_id: int, db: AsyncSession = Depends(get_db), _: Admin = Depends(mutation_admin)):
    row = await db.get(TrustedSource, source_id)
    if not row: raise HTTPException(404, "Nie znaleziono źródła")
    await db.delete(row); await db.commit(); return {"ok": True}


@router.get("/qualification/settings")
async def qualification_settings(db: AsyncSession = Depends(get_db), _: Admin = Depends(current_admin)):
    row = await db.get(AppSetting, "drop_qualification_rules")
    return {**DEFAULT_RULES, **(row.value if row else {})}


@router.put("/qualification/settings")
async def save_qualification_settings(data: dict, db: AsyncSession = Depends(get_db), _: Admin = Depends(mutation_admin)):
    allowed = set(DEFAULT_RULES); clean = {k: v for k, v in data.items() if k in allowed}
    approve = int(clean.get("approve_threshold", 85)); review = int(clean.get("review_threshold", 55))
    if not 0 <= review <= approve <= 100: raise HTTPException(422, "Nieprawidłowe progi punktacji")
    row = await db.get(AppSetting, "drop_qualification_rules")
    if not row: row = AppSetting(key="drop_qualification_rules", value={}); db.add(row)
    row.value = {**DEFAULT_RULES, **clean}; await db.commit(); return row.value


@router.get("/archive/settings")
async def archive_settings(db: AsyncSession = Depends(get_db), _: Admin = Depends(current_admin)):
    row = await db.get(AppSetting, "auto_archive_ended")
    return {"enabled": True if row is None else bool(row.value.get("enabled", True))}


@router.put("/archive/settings")
async def save_archive_settings(data: dict, db: AsyncSession = Depends(get_db), _: Admin = Depends(mutation_admin)):
    row = await db.get(AppSetting, "auto_archive_ended")
    if not row: row = AppSetting(key="auto_archive_ended", value={}); db.add(row)
    row.value = {"enabled": bool(data.get("enabled", True))}
    await db.commit(); return row.value


@router.get("/decision-history")
async def decision_history(db: AsyncSession = Depends(get_db), _: Admin = Depends(current_admin)):
    rows = (await db.execute(select(DecisionHistory).order_by(DecisionHistory.created_at.desc()).limit(300))).scalars().all()
    return [{"id": x.id, "detected_event_id": x.detected_event_id, "decision": x.decision,
             "score": x.score, "reward_value": x.reward_value, "reason": x.reason,
             "score_breakdown": x.score_breakdown, "matched_keywords": x.matched_keywords,
             "actor": x.actor, "action": x.action, "created_at": x.created_at} for x in rows]


@router.post("/sources/sync")
async def source_sync(db: AsyncSession = Depends(get_db), _: Admin = Depends(mutation_admin)):
    result = await sync_official_sources(db)
    if result.get("created"):
        try: await send_external("Nowe oficjalne informacje WoT", f"Wykryto propozycje: {result['created']}")
        except Exception: pass
    return result


@router.get("/calendar")
async def calendar(db: AsyncSession = Depends(get_db), _: Admin = Depends(current_admin)):
    now = datetime.now(UTC); end = now + timedelta(days=30); result = []
    campaigns = (await db.execute(select(Campaign).where(
        Campaign.archived.is_(False), Campaign.freshness_status.in_(ACTIVE_FRESHNESS),
        or_(Campaign.ends_at.is_(None), Campaign.ends_at >= now),
        or_(Campaign.starts_at.is_(None), Campaign.starts_at <= end),
    ))).scalars().all()
    for item in campaigns:
        result.append({"id": f"campaign-{item.id}", "title": item.title, "type": "drops", "source": item.source_type,
                       "starts_at": item.starts_at, "ends_at": item.ends_at, "status": "confirmed", "url": item.link_url})
    detected = (await db.execute(select(DetectedEvent).where(DetectedEvent.starts_at >= now,
        DetectedEvent.starts_at <= end, DetectedEvent.status == DetectionStatus.pending,
        DetectedEvent.freshness_status.in_(ACTIVE_FRESHNESS)))).scalars().all()
    for item in detected:
        result.append({"id": f"detected-{item.id}", "title": item.title, "type": item.event_type, "source": "automatic",
                       "starts_at": item.starts_at, "ends_at": item.ends_at, "status": "pending", "url": item.source_url})
    return sorted(result, key=lambda x: x["starts_at"] or datetime.max.replace(tzinfo=UTC))


class ChannelIn(BaseModel):
    login: str = Field(pattern=r"^[A-Za-z0-9_]{3,100}$")


class DropsVerification(BaseModel):
    confirmed: bool
    source_url: HttpUrl | None = None


class DiscordConfig(BaseModel):
    webhook_url: HttpUrl | None = None


@router.get("/notifications/discord")
async def discord_status(db: AsyncSession = Depends(get_db), _: Admin = Depends(current_admin)):
    row = await db.get(AppSetting, "discord_webhook")
    return {"configured": bool(row and row.value.get("encrypted"))}


@router.put("/notifications/discord")
async def discord_config(data: DiscordConfig, db: AsyncSession = Depends(get_db), _: Admin = Depends(mutation_admin)):
    row = await db.get(AppSetting, "discord_webhook")
    if not row: row = AppSetting(key="discord_webhook", value={}); db.add(row)
    row.value = {"encrypted": encrypt_token(str(data.webhook_url))} if data.webhook_url else {}
    await db.commit(); return {"configured": bool(data.webhook_url)}


@router.get("/channels")
async def channels(db: AsyncSession = Depends(get_db), _: Admin = Depends(current_admin)):
    return [{"id": x.id, "login": x.login, "drops_confirmed": x.drops_confirmed,
             "drops_source_url": x.drops_source_url, "drops_verified_at": x.drops_verified_at}
            for x in (await db.execute(select(WatchedChannel).order_by(WatchedChannel.login))).scalars().all()]


@router.post("/channels", status_code=201)
async def add_channel(data: ChannelIn, db: AsyncSession = Depends(get_db), _: Admin = Depends(mutation_admin)):
    login = data.login.lower()
    if await db.scalar(select(WatchedChannel).where(WatchedChannel.login == login)): raise HTTPException(409, "Kanał już istnieje")
    row = WatchedChannel(login=login); db.add(row); await db.commit(); return {"ok": True}


@router.delete("/channels/{channel_id}")
async def remove_channel(channel_id: int, db: AsyncSession = Depends(get_db), _: Admin = Depends(mutation_admin)):
    row = await db.get(WatchedChannel, channel_id)
    if not row: raise HTTPException(404, "Nie znaleziono kanału")
    await db.delete(row); await db.commit(); return {"ok": True}


@router.patch("/channels/{channel_id}/drops")
async def verify_drops(channel_id: int, data: DropsVerification, db: AsyncSession = Depends(get_db), _: Admin = Depends(mutation_admin)):
    row = await db.get(WatchedChannel, channel_id)
    if not row: raise HTTPException(404, "Nie znaleziono kanału")
    if data.confirmed and not data.source_url: raise HTTPException(422, "Potwierdzenie Drops wymaga źródła")
    row.drops_confirmed = data.confirmed; row.drops_source_url = str(data.source_url or "")
    row.drops_verified_at = datetime.now(UTC) if data.confirmed else None
    await db.commit(); return {"ok": True}
