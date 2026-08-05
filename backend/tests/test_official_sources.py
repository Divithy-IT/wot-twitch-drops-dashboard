from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy import func, select

from app.database import SessionLocal
from app.models import DetectedEvent, DetectionStatus
from app.services import official_sources
from app.services.official_sources import classify, extract_dates, sync_official_sources

SITEMAP = b'''<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
<url><loc>https://worldoftanks.eu/pl/news/live-streams/twitch-drops-test-2026/</loc><lastmod>2026-08-05</lastmod></url>
<url><loc>https://worldoftanks.eu/pl/news/updates/micropatch/</loc><lastmod>2026-08-05</lastmod></url></urlset>'''


def test_classification_and_date_extraction():
    assert classify("Twitch Drops stream")[0] == "drops"
    assert classify("zwykła aktualizacja")[0] is None
    dates = extract_dates("Transmisja 05.08.2026 o 18:30 oraz 2026-08-06 20:00")
    assert len(dates) == 2 and dates[0].tzinfo is not None


async def test_source_sync_and_deduplication(monkeypatch):
    async def fake_fetch(client, url, cache=None):
        if "sitemap-" in url: return SITEMAP, {"etag": "test"}
        return b"Loading site please wait", {}
    monkeypatch.setattr(official_sources, "fetch", fake_fetch)
    async with SessionLocal() as db:
        first = await sync_official_sources(db); second = await sync_official_sources(db)
        assert first["created"] == 1 and second["created"] == 0
        assert await db.scalar(select(func.count()).select_from(DetectedEvent)) == 1


async def test_source_timeout_is_recorded(monkeypatch):
    async def timeout(client, url, cache=None): raise httpx.ReadTimeout("timeout")
    monkeypatch.setattr(official_sources, "fetch", timeout)
    async with SessionLocal() as db:
        result = await sync_official_sources(db)
        assert "ReadTimeout" in result["error"]


async def test_detection_reject_and_approve(client):
    setup = await client.post('/api/auth/setup', json={'username':'eventadmin','password':'very-secure-password'})
    csrf=setup.cookies['wot_csrf']; client.cookies.set('wot_session',setup.cookies['wot_session'],path='/'); client.cookies.set('wot_csrf',csrf,path='/')
    headers={'X-CSRF-Token':csrf}
    async with SessionLocal() as db:
        one=DetectedEvent(fingerprint='a'*64,title='Drops A',source_url='https://worldoftanks.eu/pl/news/a/',excerpt='x')
        two=DetectedEvent(fingerprint='b'*64,title='Drops B',source_url='https://worldoftanks.eu/pl/news/b/',excerpt='x')
        db.add_all([one,two]); await db.commit(); await db.refresh(one); await db.refresh(two); one_id=one.id; two_id=two.id
    assert (await client.post(f'/api/detected-events/{one_id}/reject',headers=headers)).status_code == 200
    now=datetime.now(UTC)
    payload={'title':'Potwierdzone Drops','description':'x','starts_at':now.isoformat(),'ends_at':(now+timedelta(hours=2)).isoformat(),'required_minutes':60,'eligible_channels':['worldoftanks'],'rewards':['Żeton'],'link_url':'https://worldoftanks.eu/pl/news/b/'}
    approved=await client.post(f'/api/detected-events/{two_id}/approve',json=payload,headers=headers)
    assert approved.status_code == 200
    async with SessionLocal() as db:
        assert (await db.get(DetectedEvent,one_id)).status == DetectionStatus.rejected
        assert (await db.get(DetectedEvent,two_id)).status == DetectionStatus.approved


async def test_calendar_30_days(client):
    setup = await client.post('/api/auth/setup', json={'username':'calendaradmin','password':'very-secure-password'})
    client.cookies.set('wot_session',setup.cookies['wot_session'],path='/'); client.cookies.set('wot_csrf',setup.cookies['wot_csrf'],path='/')
    response=await client.get('/api/calendar')
    assert response.status_code == 200 and isinstance(response.json(),list)
