import re
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AppSetting,
    Campaign,
    DecisionHistory,
    DetectedEvent,
    DetectionStatus,
    EventLog,
    ProgressSource,
    QualificationDecision,
    Reward,
    RewardValue,
    SourceType,
    TrustedSource,
)
from app.services.freshness import ACTIVE_FRESHNESS, assess_freshness

DEFAULT_RULES = {
    "enabled": True,
    "auto_high": True,
    "auto_medium": True,
    "auto_low": True,
    "auto_unknown": True,
    "require_worldoftanks_channel": False,
    "require_exact_dates": False,
    "require_watch_time": False,
    "require_trusted_source": True,
    "require_explicit_drops": True,
    "approve_threshold": 80,
    "review_threshold": 55,
    "weights": {"explicit_drops": 70, "future_or_active": 15, "official_channel": 10,
                "rewards": 5, "watch_time": 5, "dates": 5, "stream_only": -40,
                "unofficial": -30, "ended": -30, "duplicate": -50, "ignored_source": -100},
}

EXPLICIT = ("twitch drops", "drops enabled", "twitch drops enabled", "odbierz drop", "drops inventory",
            "nagrody za oglądanie", "rewards for watching", "watch and earn", "watch to earn",
            "połącz konto twitch", "link your twitch account")
WATCH = re.compile(r"(?:oglądaj|watch)[^.!?]{0,60}(\d{1,4})\s*(?:minut|min|minutes?)", re.I)
INVENTORY = ("twitch.tv/drops/inventory", "drops inventory")
HIGH = ("premium vehicle", "pojazd premium", "rental vehicle", "wypożyc", "commander", "dowódc",
        "crew member", "członek załogi", "3d style", "styl 3d", "gold", "złot", "premium account",
        "konto premium", "bonds", "obligac", "anniversary reward", "nagrod rocznic", "exclusive")
MEDIUM = ("personal reserve", "rezerw", "equipment", "wyposaż", "premium mission", "misj", "credit",
          "kredyt", "customization", "personaliz")
LOW = ("first aid kit", "aptecz", "repair kit", "zestaw napraw", "fire extinguisher", "gaśnic",
       "emblem", "emblemat", "inscription", "napis")
HISTORICAL = ("podsumowanie", "recap", "zakończył", "has ended", "powtórka", "replay")


@dataclass
class Qualification:
    score: int
    decision: QualificationDecision
    reward_value: RewardValue
    matched: list[str] = field(default_factory=list)
    breakdown: list[dict] = field(default_factory=list)
    reason: str = ""
    explicit_drops: bool = False
    trusted: bool = False


def reward_value(rewards: list[str]) -> RewardValue:
    text = " ".join(rewards).lower()
    if not text.strip(): return RewardValue.unknown
    if any(x in text for x in HIGH): return RewardValue.high
    if any(x in text for x in MEDIUM): return RewardValue.medium
    if any(x in text for x in LOW): return RewardValue.low
    return RewardValue.unknown


def extract_reward_mentions(text: str) -> list[str]:
    """Return only reward phrases literally present in source text."""
    lowered = text.lower()
    return sorted({phrase for phrase in (*HIGH, *MEDIUM, *LOW) if phrase in lowered})


def qualify(item: DetectedEvent, trusted: TrustedSource | None, rules: dict | None = None,
            duplicate: bool = False, now: datetime | None = None) -> Qualification:
    rules = {**DEFAULT_RULES, **(rules or {})}; weights = {**DEFAULT_RULES["weights"], **rules.get("weights", {})}
    now = now or datetime.now(UTC)
    text = re.sub(r"[-_/]+", " ", f"{item.title} {item.summary} {item.excerpt}".lower())
    freshness = assess_freshness(item, now)
    matched = sorted({phrase for phrase in EXPLICIT if phrase in text})
    explicit = bool(matched); breakdown = []; score = 0
    def add(key: str, label: str):
        nonlocal score
        points = weights[key]; score += points; breakdown.append({"rule": key, "points": points, "reason": label})
    if explicit: add("explicit_drops", "Jednoznaczne potwierdzenie Twitch Drops")
    watch_match = WATCH.search(text)
    if item.required_minutes or watch_match: add("watch_time", "Podano wymagany czas oglądania")
    if item.probable_rewards: add("rewards", "Podano listę nagród")
    if item.starts_at and item.ends_at: add("dates", "Podano dokładne godziny")
    ends = item.ends_at.replace(tzinfo=UTC) if item.ends_at and item.ends_at.tzinfo is None else item.ends_at
    future_or_active = freshness.status in ACTIVE_FRESHNESS
    if future_or_active: add("future_or_active", "Wydarzenie przyszłe lub trwające")
    official_channel = "worldoftanks" in text or "twitch.tv/worldoftanks" in text or bool(
        trusted and "worldoftanks" in trusted.url_pattern
    )
    if official_channel: add("official_channel", "Oficjalny kanał lub kategoria World of Tanks")
    stream_only = any(x in text for x in ("stream", "transmis", "live")) and not explicit
    if stream_only: add("stream_only", "Tylko ogólna wzmianka o transmisji")
    is_trusted = bool(trusted and trusted.enabled and not trusted.ignored)
    if not is_trusted: add("unofficial", "Brak aktywnego zaufanego źródła")
    if trusted and trusted.ignored: add("ignored_source", "Źródło oznaczone jako ignorowane")
    ended = bool(ends and ends <= now)
    historical = any(x in text for x in HISTORICAL)
    if ended or historical: add("ended", "Wydarzenie zakończone lub historyczne")
    if duplicate: add("duplicate", "Wykryto duplikat")
    score = max(0, min(score, trusted.max_trust_score if trusted else 100, 100))
    value = reward_value(item.probable_rewards)
    blockers = []
    if not is_trusted: blockers.append("brak zaufanego źródła")
    if not explicit: blockers.append("brak jednoznacznego potwierdzenia Drops")
    if freshness.status == "reference_document": blockers.append("dokument referencyjny, nie kampania")
    elif freshness.status == "historical": blockers.append("wydarzenie historyczne lub zakończone")
    if not freshness.concrete_event: blockers.append("brak konkretnego aktualnego lub przyszłego wydarzenia")
    if duplicate: blockers.append("duplikat")
    if rules["require_worldoftanks_channel"] and not official_channel: blockers.append("brak oficjalnego kanału lub kategorii")
    can_auto = rules["enabled"] and trusted and trusted.auto_approve and not blockers and freshness.status in ACTIVE_FRESHNESS
    if can_auto and score >= rules["approve_threshold"]:
        decision = QualificationDecision.auto_approve
        missing = []
        if not item.probable_rewards: missing.append("nagrody")
        if not (item.required_minutes or watch_match): missing.append("czas oglądania")
        if not item.starts_at or not item.ends_at: missing.append("dokładne godziny")
        suffix = f" Szczegóły oczekują na publikację: {', '.join(missing)}." if missing else ""
        reason = "Drops potwierdzone oficjalnie." + suffix
    elif freshness.status in {"historical", "reference_document"} or ended or historical or duplicate or stream_only or "youtube.com" in item.source_url or (
        not explicit and is_trusted and "loading site please wait" not in text
    ):
        decision = QualificationDecision.auto_ignore
        reason = "Automatycznie zignorowano: " + ", ".join(blockers or ["brak potwierdzonych Drops"])
    else:
        decision = QualificationDecision.manual_review
        reason = "Wymaga ręcznej decyzji: " + ", ".join(blockers or ["niejednoznaczna treść źródła"])
    return Qualification(score, decision, value, matched, breakdown, reason, explicit, is_trusted)


async def load_rules(db: AsyncSession) -> dict:
    row = await db.get(AppSetting, "drop_qualification_rules")
    return {**DEFAULT_RULES, **(row.value if row else {})}


async def find_trusted_source(db: AsyncSession, url: str) -> TrustedSource | None:
    rows = (await db.execute(select(TrustedSource).where(TrustedSource.enabled.is_(True)))).scalars().all()
    return max((x for x in rows if url.startswith(x.url_pattern)), key=lambda x: len(x.url_pattern), default=None)


async def apply_qualification(db: AsyncSession, item: DetectedEvent, actor: str = "automation") -> Qualification:
    trusted = await find_trusted_source(db, item.source_url)
    duplicate_campaign = await db.scalar(select(Campaign).where(
        Campaign.source_url == item.source_url, Campaign.id != (item.approved_campaign_id or -1)
    ))
    now = datetime.now(UTC)
    freshness = assess_freshness(item, now)
    item.freshness_status = freshness.status
    result = qualify(item, trusted, await load_rules(db), duplicate=bool(duplicate_campaign), now=now)
    item.qualification_decision = result.decision; item.confidence_score = result.score
    item.reward_value = result.reward_value; item.matched_keywords = result.matched
    item.score_breakdown = result.breakdown; item.decision_reason = result.reason
    item.decided_by = actor; item.decided_at = now
    item.source_verified_at = now if result.trusted else None
    if freshness.status in {"historical", "reference_document"} and item.approved_campaign_id:
        previous = await db.get(Campaign, item.approved_campaign_id)
        if previous and previous.auto_approved:
            previous.archived = True; previous.freshness_status = freshness.status
            previous.verification_reason = freshness.reason
    if result.decision == QualificationDecision.auto_ignore: item.status = DetectionStatus.rejected
    if result.decision == QualificationDecision.auto_approve and not item.approved_campaign_id:
        channels = ["worldoftanks"] if "worldoftanks" in " ".join(result.matched).lower() or "worldoftanks" in f"{item.summary} {item.excerpt}".lower() else []
        campaign = Campaign(title=item.title[:200], description=item.summary, starts_at=item.starts_at,
            ends_at=item.ends_at, required_minutes=item.required_minutes, eligible_channels=channels,
            link_url="https://www.twitch.tv/worldoftanks" if channels else item.source_url,
            source_type=SourceType.wargaming, source_url=item.source_url, source_updated_at=datetime.now(UTC),
            progress_source=ProgressSource.manual, confidence_score=result.score, reward_value=result.reward_value,
            auto_approved=True, verification_reason=result.reason, verified_at=now,
            freshness_status=freshness.status, archived=False)
        rewards = item.probable_rewards or ["Jeszcze nie podano"]
        campaign.rewards = [Reward(name=name, required_minutes=item.required_minutes or 0) for name in rewards]
        db.add(campaign); await db.flush(); item.status = DetectionStatus.approved; item.approved_campaign_id = campaign.id
        db.add(EventLog(event_type="campaign_auto_approved", message=f"Automatycznie zatwierdzono kampanię Twitch Drops: {item.title}. Wartość: {result.reward_value.value}. Pewność: {result.score}/100."))
    elif result.decision == QualificationDecision.auto_approve and item.approved_campaign_id:
        campaign = await db.get(Campaign, item.approved_campaign_id)
        if campaign and campaign.auto_approved:
            changed = []
            if item.title and campaign.title != item.title[:200]:
                campaign.title = item.title[:200]; changed.append("title")
            for field_name in ("starts_at", "ends_at", "required_minutes"):
                value = getattr(item, field_name)
                if value is not None and value != getattr(campaign, field_name):
                    setattr(campaign, field_name, value); changed.append(field_name)
            if item.probable_rewards and [x.name for x in campaign.rewards] != item.probable_rewards:
                campaign.rewards.clear()
                campaign.rewards.extend(Reward(name=name, required_minutes=item.required_minutes or 0) for name in item.probable_rewards)
                changed.append("rewards")
            campaign.confidence_score = result.score; campaign.reward_value = result.reward_value
            campaign.freshness_status = freshness.status; campaign.archived = False
            campaign.verification_reason = result.reason; campaign.source_updated_at = datetime.now(UTC)
            if changed:
                db.add(EventLog(event_type="campaign_details_updated", message=f"Uzupełniono szczegóły kampanii: {item.title}", details={"fields": changed}))
    db.add(DecisionHistory(detected_event_id=item.id, decision=result.decision, score=result.score,
        reward_value=result.reward_value, reason=result.reason, score_breakdown=result.breakdown,
        matched_keywords=result.matched, actor=actor, action="decision"))
    return result
