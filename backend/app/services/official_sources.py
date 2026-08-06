import hashlib
import html
import re
from datetime import UTC, datetime, timedelta
from html.parser import HTMLParser
from urllib.parse import urlparse
from xml.etree import ElementTree
from zoneinfo import ZoneInfo

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import Confidence, DetectedEvent, EventLog, SourceCache
from app.services.qualification import apply_qualification, extract_reward_mentions

SITEMAP_URL = "https://worldoftanks.eu/sitemap-news-pl-1.xml"
YOUTUBE_FEED_URL = "https://www.youtube.com/feeds/videos.xml?channel_id=UCh554z2-7vIA-Mf9qAameoA"
WARGAMING_NEWS_URL = "https://wargaming.com/en/news/"
OFFICIAL_HOSTS = {"worldoftanks.eu", "www.youtube.com", "wargaming.com"}
KEYWORDS = {
    "twitch": "stream", "drop": "drops", "stream": "stream", "transmis": "stream",
    "turniej": "tournament", "tournament": "tournament", "onslaught": "onslaught",
    "frontline": "frontline", "linia-frontu": "frontline", "battle-pass": "battle_pass",
    "przepust": "battle_pass", "arcade": "arcade", "rocznic": "anniversary",
    "anniversary": "anniversary", "promoc": "promotion", "specials": "promotion",
    "zniż": "promotion", "discount": "promotion", "bonus-code": "bonus_code",
    "kod-bonus": "bonus_code", "championship": "tournament", "cup": "tournament",
}


class MetaParser(HTMLParser):
    def __init__(self):
        super().__init__(); self.meta = {}; self.title = ""; self._title = False; self.text_parts = []
    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == "meta":
            key = values.get("property") or values.get("name")
            if key and values.get("content"): self.meta[key.lower()] = values["content"].strip()
        elif tag == "title": self._title = True
    def handle_endtag(self, tag):
        if tag == "title": self._title = False
    def handle_data(self, data):
        if self._title: self.title += data.strip()
        clean = re.sub(r"\s+", " ", data).strip()
        if clean: self.text_parts.append(clean)


def classify(text: str) -> tuple[str | None, Confidence]:
    lowered = text.lower()
    matches = [kind for word, kind in KEYWORDS.items() if word in lowered]
    if not matches: return None, Confidence.low
    kind = "drops" if "drops" in matches else matches[0]
    confidence = Confidence.high if "twitch" in lowered and "drop" in lowered else Confidence.medium
    return kind, confidence


def title_from_url(url: str) -> str:
    slug = urlparse(url).path.rstrip("/").split("/")[-1]
    return " ".join(word.capitalize() for word in slug.replace("_", "-").split("-") if not word.isdigit())


def extract_dates(text: str) -> list[datetime]:
    results = []
    warsaw = ZoneInfo("Europe/Warsaw")
    patterns = [r"\b(20\d{2})-(\d{2})-(\d{2})[ T](\d{1,2}):(\d{2})\b",
                r"\b(\d{1,2})[.](\d{1,2})[.](20\d{2})[ ,T]+(?:o )?(\d{1,2}):(\d{2})\b"]
    for index, pattern in enumerate(patterns):
        for match in re.finditer(pattern, text):
            values = [int(x) for x in match.groups()]
            year, month, day, hour, minute = values if index == 0 else (values[2], values[1], values[0], values[3], values[4])
            try: results.append(datetime(year, month, day, hour, minute, tzinfo=warsaw).astimezone(UTC))
            except ValueError: continue
    return sorted(set(results))


async def fetch(client: httpx.AsyncClient, url: str, cache: SourceCache | None = None) -> tuple[bytes | None, dict]:
    if urlparse(url).hostname not in OFFICIAL_HOSTS: raise ValueError("Dozwolone są wyłącznie oficjalne źródła World of Tanks")
    headers = {"User-Agent": get_settings().source_user_agent, "Accept": "application/xml,text/html;q=0.9"}
    if cache and cache.etag: headers["If-None-Match"] = cache.etag
    if cache and cache.last_modified: headers["If-Modified-Since"] = cache.last_modified
    response = await client.get(url, headers=headers, follow_redirects=True)
    if response.status_code == 304: return None, dict(response.headers)
    response.raise_for_status()
    return response.content, dict(response.headers)


async def reanalyze_detected_event(db: AsyncSession, item: DetectedEvent) -> DetectedEvent:
    """Refresh one proposal from its official page without inventing missing facts."""
    now = datetime.now(UTC)
    if item.title.lower().startswith("loading site please wait"):
        item.title = title_from_url(item.source_url)[:300]
    async with httpx.AsyncClient(timeout=httpx.Timeout(20, connect=8)) as client:
        body, _ = await fetch(client, item.source_url)
    if body:
        parser = MetaParser(); parser.feed(body.decode("utf-8", "ignore"))
        title = parser.meta.get("og:title") or parser.title
        summary = parser.meta.get("description") or parser.meta.get("og:description")
        if title and not title.lower().startswith("loading site please wait"): item.title = title[:300]
        if summary:
            clean = re.sub(r"\s+", " ", html.unescape(summary)).strip()
            item.summary = clean[:2000]; item.excerpt = clean[:700]
            dates = extract_dates(clean)
            item.starts_at = dates[0] if dates else None
            item.ends_at = dates[1] if len(dates) > 1 else None
        visible = " ".join(parser.text_parts)[:12000]
        if visible: item.excerpt = visible[:4000]
        item.probable_rewards = extract_reward_mentions(visible)
        kind, confidence = classify(f"{item.title} {item.summary} {visible}")
        if kind: item.event_type = kind; item.confidence = confidence
        minutes = re.search(r"(?:oglądaj|watch)[^.!?]{0,60}(\d{1,4})\s*(?:minut|min|minutes?)", visible, re.I)
        if minutes: item.required_minutes = int(minutes.group(1))
    item.last_checked_at = now
    await apply_qualification(db, item)
    db.add(EventLog(event_type="detected_event_reanalyzed", message=f"Ponownie przeanalizowano: {item.title}"))
    await db.commit(); await db.refresh(item)
    return item


async def sync_official_sources(db: AsyncSession) -> dict:
    now = datetime.now(UTC); created = 0; checked = 0
    cache = await db.get(SourceCache, SITEMAP_URL)
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(20, connect=8)) as client:
            content, headers = await fetch(client, SITEMAP_URL, cache)
            if content is None:
                cache.checked_at = now; cache.last_error = ""; await db.commit()
                result = {"created": 0, "checked": 0, "cached": True}
                return merge_results(result, await sync_wargaming_news(db, now))
            digest = hashlib.sha256(content).hexdigest()
            if not cache:
                cache = SourceCache(url=SITEMAP_URL)
                db.add(cache)
            cache.etag = headers.get("etag", ""); cache.last_modified = headers.get("last-modified", "")
            cache.content_hash = digest; cache.checked_at = now; cache.last_error = ""
            root = ElementTree.fromstring(content)
            namespace = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
            candidates = []
            for node in root.findall("s:url", namespace):
                url = node.findtext("s:loc", namespaces=namespace) or ""
                modified = node.findtext("s:lastmod", namespaces=namespace)
                kind, confidence = classify(url)
                if not kind or not modified: continue
                try: published = datetime.fromisoformat(modified).replace(tzinfo=UTC)
                except ValueError: continue
                if published < now - timedelta(days=45): continue
                candidates.append((url, published, kind, confidence))
            for url, published, kind, confidence in candidates[:30]:
                checked += 1
                existing = await db.scalar(select(DetectedEvent).where(DetectedEvent.source_url == url))
                if existing:
                    existing.last_checked_at = now
                    continue
                title = title_from_url(url); summary = "Wykryto w oficjalnej mapie aktualności World of Tanks."
                excerpt = f"Oficjalna ścieżka aktualności: {urlparse(url).path}"
                dates = []
                try:
                    body, _ = await fetch(client, url)
                    if body:
                        parser = MetaParser(); parser.feed(body.decode("utf-8", "ignore"))
                        title = parser.meta.get("og:title") or parser.title or title
                        summary = parser.meta.get("description") or parser.meta.get("og:description") or summary
                        visible = " ".join(parser.text_parts)[:12000]
                        excerpt = visible[:4000] or summary[:700]; dates = extract_dates(visible or summary)
                except (httpx.HTTPError, ValueError):
                    pass
                fingerprint = hashlib.sha256(url.rstrip("/").lower().encode()).hexdigest()
                item = DetectedEvent(fingerprint=fingerprint, title=title[:300], summary=summary[:2000],
                    published_at=published, starts_at=dates[0] if dates else None,
                    ends_at=dates[1] if len(dates)>1 else None, source_url=url, excerpt=excerpt,
                    confidence=confidence, event_type=kind, last_checked_at=now)
                item.probable_rewards = extract_reward_mentions(excerpt)
                minutes = re.search(r"(?:oglądaj|watch)[^.!?]{0,60}(\d{1,4})\s*(?:minut|min|minutes?)", excerpt, re.I)
                if minutes: item.required_minutes = int(minutes.group(1))
                db.add(item); await db.flush(); await apply_qualification(db, item)
                created += 1
            if created:
                db.add(EventLog(event_type="official_events_detected", message=f"Wykryto {created} nowych oficjalnych informacji", details={"count": created}))
            await db.commit()
            result = {"created": created, "checked": checked, "cached": False}
            return merge_results(result, await sync_wargaming_news(db, now))
    except (httpx.HTTPError, ElementTree.ParseError) as exc:
        if not cache: cache = SourceCache(url=SITEMAP_URL); db.add(cache)
        cache.checked_at = now; cache.last_error = f"{type(exc).__name__}: {str(exc)[:300]}"
        db.add(EventLog(event_type="official_source_error", level="error", message="Błąd synchronizacji oficjalnego źródła"))
        await db.commit()
        fallback = await sync_youtube_feed(db, now)
        fallback = merge_results(fallback, await sync_wargaming_news(db, now))
        fallback["portal_error"] = cache.last_error
        return fallback


def merge_results(first: dict, second: dict) -> dict:
    result = dict(first)
    result["created"] = first.get("created", 0) + second.get("created", 0)
    result["checked"] = first.get("checked", 0) + second.get("checked", 0)
    if second.get("error"): result["wargaming_error"] = second["error"]
    return result


async def sync_youtube_feed(db: AsyncSession, now: datetime | None = None) -> dict:
    now = now or datetime.now(UTC); cache = await db.get(SourceCache, YOUTUBE_FEED_URL)
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(20, connect=8)) as client:
            content, headers = await fetch(client, YOUTUBE_FEED_URL, cache)
        if content is None:
            cache.checked_at = now; cache.last_error = ""; await db.commit()
            return {"created": 0, "checked": 0, "cached": True}
        root = ElementTree.fromstring(content)
        ns = {"a": "http://www.w3.org/2005/Atom", "m": "http://search.yahoo.com/mrss/"}
        if not cache: cache = SourceCache(url=YOUTUBE_FEED_URL); db.add(cache)
        cache.etag = headers.get("etag", ""); cache.last_modified = headers.get("last-modified", "")
        cache.content_hash = hashlib.sha256(content).hexdigest(); cache.checked_at = now; cache.last_error = ""
        created = 0; checked = 0
        for entry in root.findall("a:entry", ns):
            title = entry.findtext("a:title", namespaces=ns) or ""
            description = entry.findtext("m:group/m:description", namespaces=ns) or ""
            link = entry.find("a:link[@rel='alternate']", ns)
            url = link.get("href", "") if link is not None else ""
            kind, confidence = classify(f"{title} {description}")
            if not kind or not url: continue
            checked += 1
            if await db.scalar(select(DetectedEvent).where(DetectedEvent.source_url == url)): continue
            published_text = entry.findtext("a:published", namespaces=ns)
            published = datetime.fromisoformat(published_text.replace("Z", "+00:00")) if published_text else None
            dates = extract_dates(description); excerpt = re.sub(r"\s+", " ", description).strip()[:700]
            item = DetectedEvent(fingerprint=hashlib.sha256(url.encode()).hexdigest(), title=title[:300],
                summary=excerpt[:2000], published_at=published, starts_at=dates[0] if dates else None,
                ends_at=dates[1] if len(dates)>1 else None, source_url=url,
                source_name="World of Tanks — oficjalny kanał YouTube", excerpt=excerpt,
                confidence=confidence, event_type=kind, last_checked_at=now)
            db.add(item); await db.flush(); await apply_qualification(db, item); created += 1
        if created: db.add(EventLog(event_type="official_events_detected", message=f"Wykryto {created} nowych komunikatów oficjalnego kanału WoT"))
        await db.commit(); return {"created": created, "checked": checked, "cached": False}
    except (httpx.HTTPError, ElementTree.ParseError) as exc:
        if not cache: cache = SourceCache(url=YOUTUBE_FEED_URL); db.add(cache)
        cache.checked_at = now; cache.last_error = f"{type(exc).__name__}: {str(exc)[:300]}"; await db.commit()
        return {"created": 0, "checked": 0, "error": cache.last_error}


async def sync_wargaming_news(db: AsyncSession, now: datetime | None = None) -> dict:
    now = now or datetime.now(UTC); cache = await db.get(SourceCache, WARGAMING_NEWS_URL)
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(20, connect=8)) as client:
            content, headers = await fetch(client, WARGAMING_NEWS_URL, cache)
        if content is None:
            cache.checked_at = now; cache.last_error = ""; await db.commit()
            return {"created": 0, "checked": 0, "cached": True}
        text = content.decode("utf-8", "ignore")
        if not cache: cache = SourceCache(url=WARGAMING_NEWS_URL); db.add(cache)
        cache.etag = headers.get("etag", ""); cache.last_modified = headers.get("last-modified", "")
        cache.content_hash = hashlib.sha256(content).hexdigest(); cache.checked_at = now; cache.last_error = ""
        created = 0; checked = 0; seen = set()
        pattern = re.compile(r'<a[^>]+href=["\'](?P<url>/en/news/[^"\']+)["\'][^>]*>(?P<title>.*?)</a>', re.I | re.S)
        for match in pattern.finditer(text):
            url = "https://wargaming.com" + match.group("url")
            title = html.unescape(re.sub(r"<[^>]+>", " ", match.group("title")))
            title = re.sub(r"\s+", " ", title).strip()
            if not title or url in seen: continue
            seen.add(url)
            if "world of tanks" not in title.lower() and "wot" not in title.lower(): continue
            kind, confidence = classify(title)
            if not kind: kind, confidence = "event", Confidence.medium
            checked += 1
            if await db.scalar(select(DetectedEvent).where(DetectedEvent.source_url == url)): continue
            item = DetectedEvent(fingerprint=hashlib.sha256(url.encode()).hexdigest(), title=title[:300],
                summary="Oficjalny komunikat Wargaming dotyczący World of Tanks.", source_url=url,
                source_name="Wargaming News", excerpt=title[:700], confidence=confidence,
                event_type=kind, last_checked_at=now)
            db.add(item); await db.flush(); await apply_qualification(db, item); created += 1
        await db.commit(); return {"created": created, "checked": checked, "cached": False}
    except (httpx.HTTPError, ElementTree.ParseError) as exc:
        if not cache: cache = SourceCache(url=WARGAMING_NEWS_URL); db.add(cache)
        cache.checked_at = now; cache.last_error = f"{type(exc).__name__}: {str(exc)[:300]}"; await db.commit()
        return {"created": 0, "checked": 0, "error": cache.last_error}
