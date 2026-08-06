from datetime import UTC, datetime, timedelta

from app.models import DetectedEvent
from app.services.freshness import assess_freshness

NOW = datetime(2026, 8, 6, 12, tzinfo=UTC)


def item(**overrides):
    values = dict(fingerprint="f" * 64, title="World of Tanks event", summary="", excerpt="",
                  source_url="https://worldoftanks.eu/news/test", published_at=NOW)
    values.update(overrides)
    return DetectedEvent(**values)


def test_may_stream_is_historical_in_august():
    assert assess_freshness(item(title="Stream 20 May 2026"), NOW).status == "historical"


def test_july_finished_article_is_historical():
    assert assess_freshness(item(title="Lipiec 2026 — podsumowanie finałów"), NOW).status == "historical"


def test_september_campaign_is_future_announcement():
    result = assess_freshness(item(title="Twitch Drops September 2026", published_at=NOW-timedelta(days=10)), NOW)
    assert result.status == "recent_announcement"


def test_campaign_active_today():
    result = assess_freshness(item(starts_at=NOW-timedelta(hours=1), ends_at=NOW+timedelta(hours=4)), NOW)
    assert result.status == "active"


def test_fresh_announcement_without_date():
    result = assess_freshness(item(title="Upcoming Onslaught Twitch Drops", published_at=NOW-timedelta(days=2)), NOW)
    assert result.status == "unknown_date_recent"


def test_old_announcement_without_date_is_historical():
    result = assess_freshness(item(title="Upcoming Twitch Drops", published_at=NOW-timedelta(days=31)), NOW)
    assert result.status == "historical"


def test_guides_and_faq_are_reference_documents():
    assert assess_freshness(item(title="Twitch Drops Guide"), NOW).status == "reference_document"
    assert assess_freshness(item(title="Drops FAQ"), NOW).status == "reference_document"


def test_publication_date_is_not_event_date():
    result = assess_freshness(item(published_at=NOW-timedelta(days=2)), NOW)
    assert result.status == "historical"


def test_polish_and_english_past_months_without_year_do_not_roll_forward():
    assert assess_freshness(item(title="Dropy w maju"), NOW).status == "historical"
    assert assess_freshness(item(title="Drops in July"), NOW).status == "historical"


def test_recurring_event_needs_current_occurrence_signal():
    old = item(title="Weekly Drops May 2026")
    current = item(title="Weekly Drops active now", starts_at=NOW-timedelta(hours=1), ends_at=NOW+timedelta(hours=1))
    assert assess_freshness(old, NOW).status == "historical"
    assert assess_freshness(current, NOW).status == "active"
