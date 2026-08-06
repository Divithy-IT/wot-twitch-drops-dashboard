from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select

from app.database import SessionLocal
from app.models import Campaign, DetectedEvent, QualificationDecision, RewardValue, TrustedSource
from app.services.qualification import apply_qualification, qualify, reward_value


def event(**overrides):
    now = datetime.now(UTC)
    values = dict(fingerprint="q" * 64, title="Twitch Drops — watch 60 minutes",
        summary="Twitch Drops enabled on twitch.tv/worldoftanks. Watch 60 minutes.",
        excerpt="Drops Inventory", starts_at=now + timedelta(hours=2), ends_at=now + timedelta(days=2),
        required_minutes=60, probable_rewards=["Premium vehicle"],
        source_url="https://worldoftanks.eu/pl/news/drops/test/", source_name="World of Tanks EU")
    values.update(overrides); return DetectedEvent(**values)


def source(**overrides):
    values = dict(name="WoT", url_pattern="https://worldoftanks.eu/", enabled=True,
                  auto_approve=True, max_trust_score=100, ignored=False)
    values.update(overrides); return TrustedSource(**values)


def test_confirmed_high_value_drops_auto_approve():
    result = qualify(event(), source())
    assert result.decision == QualificationDecision.auto_approve
    assert result.score == 100 and result.reward_value == RewardValue.high


def test_plain_stream_is_ignored():
    result = qualify(event(title="Zwykła transmisja", summary="Oglądaj nasz stream live", excerpt="",
                           required_minutes=None, probable_rewards=[], starts_at=None, ends_at=None), source())
    assert result.decision == QualificationDecision.auto_ignore
    assert result.score == 0


def test_official_news_without_literal_drops_is_ignored():
    result = qualify(event(title="Aktualizacja gry", summary="Nowa wersja World of Tanks", excerpt="",
                           event_type="event", required_minutes=None, probable_rewards=[],
                           starts_at=None, ends_at=None), source())
    assert result.decision == QualificationDecision.auto_ignore


def test_historical_and_duplicate_are_ignored():
    old = event(summary="Twitch Drops — podsumowanie zakończonej kampanii",
                starts_at=datetime.now(UTC)-timedelta(days=3), ends_at=datetime.now(UTC)-timedelta(days=1))
    assert qualify(old, source()).decision == QualificationDecision.auto_ignore
    assert qualify(event(), source(), duplicate=True).decision == QualificationDecision.auto_ignore


def test_unofficial_needs_review_but_missing_rewards_do_not_block():
    assert qualify(event(), None).decision == QualificationDecision.manual_review
    unknown = qualify(event(probable_rewards=[]), source())
    assert unknown.reward_value == RewardValue.unknown and unknown.decision == QualificationDecision.auto_approve


def test_reward_levels_are_conservative():
    assert reward_value(["Premium vehicle"]) == RewardValue.high
    assert reward_value(["Personal reserves"]) == RewardValue.medium
    assert reward_value(["Repair kit"]) == RewardValue.low
    assert reward_value(["Mystery reward"]) == RewardValue.unknown


def test_low_value_does_not_block_official_drops():
    result = qualify(event(probable_rewards=["Repair kit"]), source())
    assert result.reward_value == RewardValue.low and result.decision == QualificationDecision.auto_approve


def test_official_drops_without_watch_time_are_approved():
    result = qualify(event(required_minutes=None, summary="Twitch Drops enabled for World of Tanks"), source())
    assert result.decision == QualificationDecision.auto_approve and result.score >= 80


def test_official_drops_with_date_only_are_approved():
    day = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=2)
    result = qualify(event(starts_at=day, ends_at=None, required_minutes=None, probable_rewards=[]), source())
    assert result.decision == QualificationDecision.auto_approve


def test_official_structured_url_can_confirm_twitch_drops():
    item = event(title="Loading site please wait...", summary="", excerpt="", starts_at=None,
                 ends_at=None, required_minutes=None, probable_rewards=[],
                 source_url="https://worldoftanks.eu/pl/news/guides-reviews/twitch-drops-guide/")
    result = qualify(item, source())
    assert result.decision == QualificationDecision.auto_approve and result.score == 80


async def test_apply_creates_campaign_and_history_once():
    async with SessionLocal() as db:
        trusted = source(); item = event(); db.add_all([trusted, item]); await db.flush()
        result = await apply_qualification(db, item); await db.commit()
        assert result.decision == QualificationDecision.auto_approve
        assert await db.scalar(select(func.count()).select_from(Campaign)) == 1


async def test_later_details_update_existing_campaign():
    async with SessionLocal() as db:
        trusted = source(); item = event(required_minutes=None, probable_rewards=[], ends_at=None)
        db.add_all([trusted, item]); await db.flush(); await apply_qualification(db, item); await db.commit()
        campaign = await db.get(Campaign, item.approved_campaign_id)
        assert campaign.required_minutes is None and campaign.reward_value == RewardValue.unknown
        item.required_minutes = 90; item.probable_rewards = ["Premium vehicle"]
        item.ends_at = datetime.now(UTC) + timedelta(days=3)
        await apply_qualification(db, item); await db.commit(); await db.refresh(campaign)
        assert campaign.required_minutes == 90 and campaign.ends_at is not None
        await apply_qualification(db, item); await db.commit()
        assert await db.scalar(select(func.count()).select_from(Campaign)) == 1
