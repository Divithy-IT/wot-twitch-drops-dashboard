import asyncio
import json
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import current_admin, mutation_admin
from app.database import get_db
from app.models import Admin, Campaign, EventLog, Reward
from app.schemas import CampaignIn, CampaignOut, ProgressIn

router = APIRouter(prefix="/campaigns", tags=["campaigns"])


def status_of(c: Campaign, now: datetime | None = None) -> str:
    now = now or datetime.now(UTC)
    starts_at = c.starts_at.replace(tzinfo=UTC) if c.starts_at.tzinfo is None else c.starts_at
    ends_at = c.ends_at.replace(tzinfo=UTC) if c.ends_at.tzinfo is None else c.ends_at
    return "upcoming" if now < starts_at else "active" if now < ends_at else "ended"


def seconds_remaining(c: Campaign, now: datetime | None = None) -> int:
    now = now or datetime.now(UTC)
    starts_at = c.starts_at.replace(tzinfo=UTC) if c.starts_at.tzinfo is None else c.starts_at
    ends_at = c.ends_at.replace(tzinfo=UTC) if c.ends_at.tzinfo is None else c.ends_at
    target = starts_at if now < starts_at else ends_at
    return max(0, int((target - now).total_seconds()))


async def fetch(db: AsyncSession, campaign_id: int) -> Campaign:
    result = await db.execute(select(Campaign).options(selectinload(Campaign.rewards)).where(Campaign.id == campaign_id))
    campaign = result.scalar_one_or_none()
    if not campaign: raise HTTPException(404, "Nie znaleziono kampanii")
    return campaign


@router.get("")
async def list_campaigns(db: AsyncSession = Depends(get_db), _: Admin = Depends(current_admin)):
    now = datetime.now(UTC)
    rows = (await db.execute(select(Campaign).options(selectinload(Campaign.rewards)).where(
        Campaign.ends_at >= now - timedelta(days=90), Campaign.starts_at <= now + timedelta(days=30)
    ).order_by(Campaign.starts_at))).scalars().unique().all()
    return [{**CampaignOut.model_validate(c).model_dump(mode="json"), "status": status_of(c),
             "seconds_remaining": seconds_remaining(c)} for c in rows]


@router.post("", status_code=201)
async def create(data: CampaignIn, db: AsyncSession = Depends(get_db), _: Admin = Depends(mutation_admin)):
    values = data.model_dump(exclude={"rewards"})
    values["link_url"] = str(data.link_url); values["source_url"] = str(data.source_url or "")
    campaign = Campaign(**values)
    campaign.rewards = [Reward(**r.model_dump()) for r in data.rewards]
    db.add(campaign); await db.flush()
    db.add(EventLog(event_type="campaign_created", message=f"Dodano kampanię: {campaign.title}", details={"id": campaign.id}))
    await db.commit(); await db.refresh(campaign)
    return {"id": campaign.id}


@router.put("/{campaign_id}")
async def update(campaign_id: int, data: CampaignIn, db: AsyncSession = Depends(get_db), _: Admin = Depends(mutation_admin)):
    campaign = await fetch(db, campaign_id)
    for key, value in data.model_dump(exclude={"rewards"}).items():
        if key in {"link_url", "source_url"}:
            value = str(value or "")
        setattr(campaign, key, value)
    await db.execute(delete(Reward).where(Reward.campaign_id == campaign_id))
    campaign.rewards = [Reward(**r.model_dump()) for r in data.rewards]
    campaign.source_updated_at = datetime.now(UTC)
    db.add(EventLog(event_type="campaign_updated", message=f"Zmieniono kampanię: {campaign.title}"))
    await db.commit()
    return {"ok": True}


@router.delete("/{campaign_id}")
async def remove(campaign_id: int, db: AsyncSession = Depends(get_db), _: Admin = Depends(mutation_admin)):
    campaign = await fetch(db, campaign_id); await db.delete(campaign); await db.commit(); return {"ok": True}


@router.patch("/{campaign_id}/progress")
async def progress(campaign_id: int, data: ProgressIn, db: AsyncSession = Depends(get_db), _: Admin = Depends(mutation_admin)):
    campaign = await fetch(db, campaign_id)
    campaign.watched_minutes = data.watched_minutes; campaign.progress_source = data.source
    campaign.last_progress_at = datetime.now(UTC)
    for reward in campaign.rewards:
        if data.watched_minutes >= reward.required_minutes and not reward.earned:
            reward.earned = True
            db.add(EventLog(event_type="reward_earned", message=f"Zdobyto: {reward.name}"))
    await db.commit(); return {"ok": True}


@router.patch("/{campaign_id}/rewards/{reward_id}")
async def reward_state(campaign_id: int, reward_id: int, earned: bool, claimed: bool,
                       db: AsyncSession = Depends(get_db), _: Admin = Depends(mutation_admin)):
    reward = await db.get(Reward, reward_id)
    if not reward or reward.campaign_id != campaign_id: raise HTTPException(404, "Nie znaleziono nagrody")
    reward.earned = earned; reward.claimed = claimed; await db.commit(); return {"ok": True}


@router.get("/events/stream")
async def events(_: Admin = Depends(current_admin)):
    async def generate():
        while True:
            yield f"event: heartbeat\ndata: {json.dumps({'at': datetime.now(UTC).isoformat()})}\n\n"
            await asyncio.sleep(30)
    return StreamingResponse(generate(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})
