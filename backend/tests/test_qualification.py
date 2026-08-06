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


def test_historical_and_duplicate_are_ignored():
    old = event(summary="Twitch Drops — podsumowanie zakończonej kampanii",
                starts_at=datetime.now(UTC)-timedelta(days=3), ends_at=datetime.now(UTC)-timedelta(days=1))
    assert qualify(old, source()).decision == QualificationDecision.auto_ignore
    assert qualify(event(), source(), duplicate=True).decision == QualificationDecision.auto_ignore


def test_unofficial_and_missing_rewards_need_review():
    assert qualify(event(), None).decision == QualificationDecision.manual_review
    unknown = qualify(event(probable_rewards=[]), source())
    assert unknown.reward_value == RewardValue.unknown and unknown.decision == QualificationDecision.manual_review


def test_reward_levels_are_conservative():
    assert reward_value(["Premium vehicle"]) == RewardValue.high
    assert reward_value(["Personal reserves"]) == RewardValue.medium
    assert reward_value(["Repair kit"]) == RewardValue.low
    assert reward_value(["Mystery reward"]) == RewardValue.unknown


def test_low_value_requires_manual_review_by_default():
    result = qualify(event(probable_rewards=["Repair kit"]), source())
    assert result.reward_value == RewardValue.low and result.decision == QualificationDecision.manual_review


async def test_apply_creates_campaign_and_history_once():
    async with SessionLocal() as db:
        trusted = source(); item = event(); db.add_all([trusted, item]); await db.flush()
        result = await apply_qualification(db, item); await db.commit()
        assert result.decision == QualificationDecision.auto_approve
        assert await db.scalar(select(func.count()).select_from(Campaign)) == 1
        await apply_qualification(db, item); await db.commit()
        assert await db.scalar(select(func.count()).select_from(Campaign)) == 1
