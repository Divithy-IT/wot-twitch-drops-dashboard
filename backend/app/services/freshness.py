import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from app.models import DetectedEvent

ACTIVE_FRESHNESS = {"active", "upcoming", "recent_announcement", "unknown_date_recent"}
REFERENCE = (
    "twitch drops guide", "how to earn twitch drops", "drops faq", "how to link your twitch account",
    "drops technical guide", "twitch drops explained", "drops guide", "poradnik twitch drops",
    "jak zdobyć twitch drops", "jak połączyć konto twitch", "faq",
)
PAST_LANGUAGE = (
    "odbyło się", "oglądaliście", "były dostępne", "mogliście zdobyć", "podczas transmisji rozdaliśmy",
    "zakończyło się", "wyniki finałów", "podsumowanie", "replay", " vod ", "recap", "highlights",
    "has ended", "were available", "you could earn",
)
FUTURE_LANGUAGE = (
    "nadchodząc", "wkrótce", "już wkrótce", "this weekend", "tomorrow", "jutro", "upcoming",
    "will be available", "will feature", "starts", "rozpocznie", "odbędą się", "zapraszamy",
)
ACTIVE_LANGUAGE = ("active now", "available now", "już trwa", "trwa teraz", "dzisiaj", "today")
MONTHS = {
    "styczeń": 1, "stycznia": 1, "january": 1, "luty": 2, "lutego": 2, "february": 2,
    "marzec": 3, "marca": 3, "march": 3, "kwiecień": 4, "kwietnia": 4, "april": 4,
    "maj": 5, "maja": 5, "may": 5, "czerwiec": 6, "czerwca": 6, "june": 6,
    "lipiec": 7, "lipca": 7, "july": 7, "sierpień": 8, "sierpnia": 8, "august": 8,
    "wrzesień": 9, "września": 9, "september": 9, "październik": 10, "października": 10,
    "october": 10, "listopad": 11, "listopada": 11, "november": 11,
    "grudzień": 12, "grudnia": 12, "december": 12,
}


@dataclass
class Freshness:
    status: str
    reason: str
    concrete_event: bool


def aware(value: datetime | None) -> datetime | None:
    if value is None: return None
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


def mentioned_months(text: str) -> list[tuple[int, int | None]]:
    found = []
    for name, month in MONTHS.items():
        for match in re.finditer(rf"\b{re.escape(name)}\b(?:\s+(20\d{{2}}))?", text, re.I):
            year = int(match.group(1)) if match.group(1) else None
            found.append((month, year))
    return found


def assess_freshness(item: DetectedEvent, now: datetime | None = None) -> Freshness:
    now = now or datetime.now(UTC); today = now.date()
    text = re.sub(r"\s+", " ", f" {item.title} {item.summary} {item.excerpt} ".lower())
    identity = re.sub(r"[-_/]+", " ", f" {item.title} {item.source_url} ".lower())
    published = aware(item.published_at); start = aware(item.starts_at); end = aware(item.ends_at)
    # Navigation/footer text often links to a global Drops guide; only the document's own title/URL identifies it.
    if any(phrase in identity for phrase in REFERENCE):
        return Freshness("reference_document", "Ogólny poradnik lub dokument referencyjny bez konkretnej kampanii", False)
    if end and end <= now:
        return Freshness("historical", "Termin zakończenia już minął", True)
    if start and start.date() < today and not end:
        return Freshness("historical", "Data transmisji jest wcześniejsza niż aktualny dzień", True)
    if any(phrase in text for phrase in PAST_LANGUAGE):
        return Freshness("historical", "Treść opisuje zakończone wydarzenie, nagranie lub podsumowanie", True)
    months = mentioned_months(text)
    if any((year is not None and (year, month) < (today.year, today.month)) or
           (year is None and month < today.month) for month, year in months):
        return Freshness("historical", "Treść wskazuje miesiąc, który już minął", True)
    if "youtube.com" in item.source_url and published and published.date() < today and not any(x in text for x in FUTURE_LANGUAGE):
        return Freshness("historical", "Opublikowany wcześniej materiał YouTube nie zapowiada nowego wydarzenia", False)
    if start and end and start <= now < end:
        return Freshness("active", "Kampania trwa obecnie", True)
    if start and now < start <= now + timedelta(days=30):
        return Freshness("upcoming", "Kampania rozpocznie się w ciągu 30 dni", True)
    future_month = any((year is not None and (year, month) > (today.year, today.month)) or
                       (year is None and month > today.month) for month, year in months)
    future_signal = any(x in text for x in FUTURE_LANGUAGE) or bool(start and start > now) or future_month
    active_signal = any(x in text for x in ACTIVE_LANGUAGE)
    age = now - published if published else None
    if published and age > timedelta(days=30) and not (start and start > now):
        return Freshness("historical", "Źródło ma ponad 30 dni i nie zawiera przyszłego terminu", False)
    if (future_signal or active_signal) and published and age <= timedelta(days=7):
        return Freshness("unknown_date_recent", "Świeże potwierdzenie nadchodzących Drops bez pełnego terminu", True)
    if future_signal and published and age <= timedelta(days=30):
        return Freshness("recent_announcement", "Świeża, jednoznaczna zapowiedź przyszłego wydarzenia", True)
    if start and start > now + timedelta(days=30):
        return Freshness("recent_announcement", "Potwierdzony przyszły termin wykracza poza widok 30 dni", True)
    return Freshness("historical", "Brak aktualnego lub przyszłego konkretnego wydarzenia", False)
