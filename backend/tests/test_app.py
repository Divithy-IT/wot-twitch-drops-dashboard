from datetime import UTC, datetime, timedelta

from app.api.campaigns import seconds_remaining, status_of
from app.models import Campaign


async def setup(client):
 r=await client.post('/api/auth/setup',json={'username':'administrator','password':'very-secure-password'})
 assert r.status_code==201
 csrf=r.cookies['wot_csrf']
 client.cookies.set('wot_session',r.cookies['wot_session'],path='/')
 client.cookies.set('wot_csrf',csrf,path='/')
 return {'X-CSRF-Token':csrf}

async def test_health_and_base_path(client):
 assert (await client.get('/api/health')).json()=={'status':'ok'}
 assert (await client.get('/')).status_code in (200,503)
 assert (await client.head('/')).status_code in (200,503)

async def test_admin_setup_login_and_rate_limit(client):
 await setup(client)
 assert (await client.post('/api/auth/setup',json={'username':'secondadmin','password':'another-secure-password'})).status_code==409
 for _ in range(5):await client.post('/api/auth/login',json={'username':'administrator','password':'incorrect-pass'})
 assert (await client.post('/api/auth/login',json={'username':'administrator','password':'incorrect-pass'})).status_code==429

async def test_campaign_crud_and_progress(client):
 h=await setup(client);now=datetime.now(UTC)
 payload={'title':'Test Drops','description':'test','starts_at':now.isoformat(),'ends_at':(now+timedelta(hours=2)).isoformat(),'required_minutes':120,'eligible_channels':['worldoftanks'],'category_name':'World of Tanks','link_url':'https://twitch.tv/worldoftanks','source_type':'manual','source_url':'https://worldoftanks.eu','rewards':[{'name':'Czołg','required_minutes':60}]}
 r=await client.post('/api/campaigns',json=payload,headers=h);assert r.status_code==201
 cid=r.json()['id'];rows=(await client.get('/api/campaigns')).json();assert rows[0]['status']=='active'
 assert (await client.patch(f'/api/campaigns/{cid}/progress',json={'watched_minutes':65,'source':'manual'},headers=h)).status_code==200
 assert (await client.get('/api/campaigns')).json()[0]['rewards'][0]['earned'] is True

def test_status_and_remaining():
 now=datetime.now(UTC);c=Campaign(title='x',starts_at=now+timedelta(minutes=5),ends_at=now+timedelta(hours=1))
 assert status_of(c,now)=='upcoming';assert 299<=seconds_remaining(c,now)<=300
 assert status_of(c,now+timedelta(minutes=10))=='active'

async def test_oauth_status_disconnected(client):
 await setup(client);r=await client.get('/api/oauth/twitch/status');assert r.json()['connected'] is False

async def test_csrf_required(client):
 await setup(client);r=await client.post('/api/auth/logout',headers={'X-CSRF-Token':'bad'});assert r.status_code==403
