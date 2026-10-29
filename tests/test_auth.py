import os
from urllib.parse import parse_qs, urlparse

os.environ.setdefault('DATABASE_URL', 'sqlite+aiosqlite:///./calllens_auth_test.db')
os.environ.setdefault('APP_BASE_URL', 'http://localhost:8000')
os.environ.setdefault('EMAIL_MODE', 'log')
os.environ.setdefault('ALLOWED_ORIGINS', 'http://localhost:8000')

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from auth_db import SessionLocal, engine
from auth_models import Base, MagicLinkToken, Session, Tenant, User
import auth_routes
from backend import app


@pytest.fixture(autouse=True)
async def clean_db():
    async with engine.begin() as conn:
        if conn.sync_connection.dialect.name == 'postgresql':
            await conn.execute(delete(Session))
            await conn.execute(delete(MagicLinkToken))
            await conn.execute(delete(User))
            await conn.execute(delete(Tenant))
        else:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)
    auth_routes.RATE_BUCKETS.clear()
    yield
    if engine.sync_engine.dialect.name != 'postgresql':
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url='http://localhost:8000') as c:
        yield c


async def seed():
    async with SessionLocal() as db:
        t1, t2 = Tenant(name='One', slug='one'), Tenant(name='Two', slug='two')
        db.add_all([t1, t2]); await db.flush()
        u1 = User(tenant_id=t1.id, email='owner@one.example.com', role='owner', full_name='Owner One')
        m1 = User(tenant_id=t1.id, email='manager@one.example.com', role='manager')
        u2 = User(tenant_id=t2.id, email='owner@two.example.com', role='owner')
        db.add_all([u1, m1, u2]); await db.commit()
        return t1, t2, u1, m1, u2


async def issue_link(client, monkeypatch, email, tenant_slug):
    sent = {}
    async def fake_send(settings, target, url, purpose): sent.update(url=url, purpose=purpose)
    monkeypatch.setattr(auth_routes, 'send_magic_link', fake_send)
    response = await client.post('/api/auth/request-link', json={'email': email, 'tenant_slug': tenant_slug})
    assert response.status_code == 202
    return parse_qs(urlparse(sent['url']).query)['token'][0]


async def authenticated_client(client, monkeypatch, email='owner@one.example.com', tenant_slug='one'):
    raw = await issue_link(client, monkeypatch, email, tenant_slug)
    verified = await client.get('/api/auth/verify', params={'token': raw}, follow_redirects=False)
    assert verified.status_code == 302
    return verified.cookies, raw


@pytest.mark.asyncio
async def test_request_link_existing_user(client, monkeypatch):
    t1, _, owner, _, _ = await seed()
    sent = {}
    async def fake_send(settings, email, url, purpose): sent.update(email=email, url=url, purpose=purpose)
    monkeypatch.setattr(auth_routes, 'send_magic_link', fake_send)
    r = await client.post('/api/auth/request-link', json={'email': owner.email, 'tenant_slug': t1.slug})
    assert r.status_code == 202 and r.json() == {'status': 'sent_if_exists'}
    async with SessionLocal() as db:
        row = await db.scalar(select(MagicLinkToken).where(MagicLinkToken.email == owner.email))
        assert row and len(row.token_hash) == 64 and row.tenant_id == t1.id


@pytest.mark.asyncio
async def test_request_link_unknown_email(client):
    await seed()
    r = await client.post('/api/auth/request-link', json={'email': 'unknown@example.com', 'tenant_slug': 'one'})
    assert r.status_code == 202
    async with SessionLocal() as db:
        assert await db.scalar(select(MagicLinkToken)) is None


@pytest.mark.asyncio
async def test_verify_valid_token(client, monkeypatch):
    await seed()
    cookies, _ = await authenticated_client(client, monkeypatch)
    assert cookies.get('session')


@pytest.mark.asyncio
async def test_verify_expired_token(client):
    await seed()
    r = await client.get('/api/auth/verify?token=does-not-exist')
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_verify_reused_token(client, monkeypatch):
    await seed()
    _, raw = await authenticated_client(client, monkeypatch)
    reused = await client.get('/api/auth/verify', params={'token': raw})
    assert reused.status_code == 400


@pytest.mark.asyncio
async def test_me_without_cookie(client):
    r = await client.get('/api/auth/me')
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_me_with_cookie(client, monkeypatch):
    await seed()
    cookies, _ = await authenticated_client(client, monkeypatch)
    me = await client.get('/api/auth/me', cookies=cookies)
    assert me.status_code == 200 and me.json()['tenant']['slug'] == 'one'
    assert me.json()['user']['email'] == 'owner@one.example.com'


@pytest.mark.asyncio
async def test_logout_revokes_session(client, monkeypatch):
    await seed()
    cookies, _ = await authenticated_client(client, monkeypatch)
    assert (await client.post('/api/auth/logout', cookies=cookies)).status_code == 200
    assert (await client.get('/api/auth/me', cookies=cookies)).status_code == 401


@pytest.mark.asyncio
async def test_tenant_isolation(client, monkeypatch):
    t1, t2, owner, _, _ = await seed()
    cookies, _ = await authenticated_client(client, monkeypatch)
    listed = await client.get('/api/users', cookies=cookies)
    assert listed.status_code == 200
    assert {u['email'] for u in listed.json()['users']} == {'owner@one.example.com', 'manager@one.example.com'}
    invite = await client.post(f'/api/tenants/{t2.id}/invite', cookies=cookies, json={'email':'x@example.com','role':'manager'})
    assert invite.status_code == 403


@pytest.mark.asyncio
async def test_tenant_isolation_direct_query():
    rls_url = os.getenv('DATABASE_URL_RLS')
    if not rls_url:
        pytest.skip('DATABASE_URL_RLS не задан для прямой PostgreSQL RLS-проверки')
    await seed()
    rls_engine = create_async_engine(rls_url, poolclass=NullPool)
    try:
        async with rls_engine.connect() as conn:
            rows = (await conn.execute(text('SELECT id, tenant_id FROM users'))).all()
            assert rows == []
    finally:
        await rls_engine.dispose()


@pytest.mark.asyncio
async def test_request_link_rate_limit(client):
    await seed()
    statuses = [(await client.post('/api/auth/request-link', json={'email':'nobody@example.com','tenant_slug':'one'})).status_code for _ in range(6)]
    assert statuses[:5] == [202] * 5 and statuses[5] == 429
