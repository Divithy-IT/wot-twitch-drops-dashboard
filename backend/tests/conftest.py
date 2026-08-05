import os

os.environ.setdefault("SECRET_KEY","x"*40)
os.environ.setdefault("TOKEN_ENCRYPTION_KEY","MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA=")
os.environ.setdefault("DATABASE_URL","sqlite+aiosqlite:///:memory:")
import pytest
from httpx import ASGITransport, AsyncClient

from app.database import Base, engine
from app.main import app


@pytest.fixture(autouse=True)
async def schema():
 async with engine.begin() as c: await c.run_sync(Base.metadata.create_all)
 yield
 async with engine.begin() as c: await c.run_sync(Base.metadata.drop_all)

@pytest.fixture
async def client():
 async with AsyncClient(transport=ASGITransport(app=app),base_url="http://test") as c: yield c
