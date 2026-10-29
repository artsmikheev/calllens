import hashlib
import logging
import secrets
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, Cookie, Depends, Header, HTTPException, Request, Response
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from auth_db import get_db, set_tenant_scope
from auth_mail import send_magic_link
from auth_models import MagicLinkToken, Session, Tenant, User
from auth_settings import get_settings

logger = logging.getLogger('calllens.auth')
router = APIRouter()
ROOT = Path(__file__).parent
RATE_BUCKETS: dict[str, deque[datetime]] = defaultdict(deque)
ROLES = {'owner', 'rop', 'manager', 'analyst'}


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def as_aware(value: datetime | None) -> datetime | None:
    if value is None or value.tzinfo is not None:
        return value
    return value.replace(tzinfo=timezone.utc)


def token_hash(raw: str) -> str:
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()


def email_norm(value: str) -> str:
    return value.strip().lower()


def user_out(user: User) -> dict:
    return {'id': str(user.id), 'email': user.email, 'full_name': user.full_name, 'role': user.role, 'tenant_id': str(user.tenant_id)}


def tenant_out(tenant: Tenant) -> dict:
    return {'id': str(tenant.id), 'name': tenant.name, 'slug': tenant.slug, 'plan': tenant.plan}


class LinkRequest(BaseModel):
    email: EmailStr
    tenant_slug: str | None = None


class InviteRequest(BaseModel):
    email: EmailStr
    role: str = 'manager'
    manager_id: UUID | None = None


class UserPatch(BaseModel):
    role: str | None = None
    manager_id: UUID | None = None
    full_name: str | None = None
    deleted_at: datetime | None = None


async def csrf_guard(request: Request, origin: str | None = Header(default=None)) -> None:
    if origin and origin.rstrip('/') not in get_settings().allowed_origin_list:
        raise HTTPException(403, 'Недопустимый Origin')


def rate_limit(ip: str) -> None:
    now = utcnow(); bucket = RATE_BUCKETS[ip]
    while bucket and (now - bucket[0]).total_seconds() >= 60:
        bucket.popleft()
    if len(bucket) >= 5:
        raise HTTPException(429, 'Слишком много запросов. Попробуйте позже.')
    bucket.append(now)


async def current_context(request: Request, db: AsyncSession = Depends(get_db), session_cookie: str | None = Cookie(default=None, alias='session')) -> tuple[User, Tenant, Session]:
    if not session_cookie:
        raise HTTPException(401, 'Требуется вход')
    row = await db.scalar(select(Session).where(Session.token_hash == token_hash(session_cookie), Session.revoked_at.is_(None)))
    if not row or not as_aware(row.expires_at) or as_aware(row.expires_at) <= utcnow():
        raise HTTPException(401, 'Сессия истекла или отозвана')
    await set_tenant_scope(db, str(row.tenant_id))
    user = await db.scalar(select(User).where(User.id == row.user_id, User.tenant_id == row.tenant_id, User.deleted_at.is_(None)))
    if not user:
        raise HTTPException(401, 'Пользователь недоступен')
    await set_tenant_scope(db, str(user.tenant_id))
    tenant = await db.scalar(select(Tenant).where(Tenant.id == user.tenant_id, Tenant.deleted_at.is_(None)))
    if not tenant:
        raise HTTPException(401, 'Тенант недоступен')
    request.state.current_user = user
    request.state.current_tenant = tenant
    return user, tenant, row


def require_roles(user: User, allowed: set[str]) -> None:
    if user.role not in allowed:
        raise HTTPException(403, 'Недостаточно прав')


@router.get('/login', include_in_schema=False)
async def login_page():
    return FileResponse(ROOT / 'login.html')


@router.get('/app', include_in_schema=False)
async def app_page():
    return FileResponse(ROOT / 'app-home.html')


@router.post('/api/auth/request-link', status_code=202)
async def request_link(payload: LinkRequest, request: Request, _csrf=Depends(csrf_guard), db: AsyncSession = Depends(get_db)):
    rate_limit(request.client.host if request.client else 'unknown')
    user = None
    email = email_norm(str(payload.email))
    if payload.tenant_slug:
        tenant = await db.scalar(select(Tenant).where(Tenant.slug == payload.tenant_slug.strip().lower(), Tenant.deleted_at.is_(None)))
        if tenant:
            await set_tenant_scope(db, str(tenant.id))
            user = await db.scalar(select(User).where(User.tenant_id == tenant.id, User.email == email, User.deleted_at.is_(None)))
    else:
        users = (await db.scalars(select(User).where(User.email == email, User.deleted_at.is_(None)))).all()
        if len(users) == 1:
            user = users[0]
    if user:
        settings = get_settings(); raw = secrets.token_urlsafe(32)
        token = MagicLinkToken(user_id=user.id, tenant_id=user.tenant_id, email=email, token_hash=token_hash(raw), purpose='login', expires_at=utcnow() + timedelta(minutes=settings.magic_link_ttl_minutes))
        db.add(token); await db.commit()
        url = f"{settings.app_base_url.rstrip('/')}/api/auth/verify?token={quote(raw)}"
        await send_magic_link(settings, email, url, 'login')
    return {'status': 'sent_if_exists'}


@router.get('/api/auth/verify')
async def verify_link(token: str, request: Request, db: AsyncSession = Depends(get_db)):
    row = await db.scalar(select(MagicLinkToken).where(MagicLinkToken.token_hash == token_hash(token)))
    if not row or row.used_at is not None or not as_aware(row.expires_at) or as_aware(row.expires_at) <= utcnow():
        return HTMLResponse('<h1>Ссылка недействительна или истекла.</h1><p><a href="/login">Запросить новую</a></p>', status_code=400)
    if row.user_id is None:
        return HTMLResponse('<h1>Приглашение не связано с пользователем.</h1><p><a href="/login">Перейти ко входу</a></p>', status_code=400)
    if row.tenant_id:
        await set_tenant_scope(db, str(row.tenant_id))
    user = await db.scalar(select(User).where(User.id == row.user_id, User.tenant_id == row.tenant_id, User.deleted_at.is_(None)))
    if not user:
        return HTMLResponse('<h1>Пользователь недоступен.</h1><p><a href="/login">Перейти ко входу</a></p>', status_code=400)
    row.used_at = utcnow()
    raw_session = secrets.token_urlsafe(40); settings = get_settings()
    db.add(Session(user_id=user.id, tenant_id=user.tenant_id, token_hash=token_hash(raw_session), user_agent=request.headers.get('user-agent'), expires_at=utcnow() + timedelta(days=settings.session_ttl_days)))
    user.last_login_at = utcnow(); await db.commit()
    response = RedirectResponse('/app', status_code=302)
    response.set_cookie(settings.auth_cookie_name, raw_session, max_age=settings.session_ttl_days * 86400, httponly=True, secure=settings.cookie_secure, samesite='lax', path='/')
    return response


@router.post('/api/auth/logout')
async def logout(response: Response, request: Request, ctx=Depends(current_context), _csrf=Depends(csrf_guard), db: AsyncSession = Depends(get_db)):
    _, _, session = ctx
    session.revoked_at = utcnow(); await db.commit()
    response.delete_cookie(get_settings().auth_cookie_name, path='/')
    return {'status': 'ok'}


@router.get('/api/auth/me')
async def me(ctx=Depends(current_context)):
    user, tenant, _ = ctx
    return {'user': user_out(user), 'tenant': tenant_out(tenant)}


@router.post('/api/tenants/{tenant_id}/invite', status_code=201)
async def invite(tenant_id: UUID, payload: InviteRequest, request: Request, ctx=Depends(current_context), _csrf=Depends(csrf_guard), db: AsyncSession = Depends(get_db)):
    user, tenant, _ = ctx
    if user.tenant_id != tenant_id:
        raise HTTPException(403, 'Нельзя приглашать пользователя в другой тенант')
    require_roles(user, {'owner', 'rop'})
    if payload.role not in ROLES:
        raise HTTPException(422, 'Недопустимая роль')
    if user.role == 'rop' and payload.role != 'manager':
        raise HTTPException(403, 'ROП может приглашать только manager')
    email = email_norm(str(payload.email))
    existing = await db.scalar(select(User).where(User.tenant_id == tenant_id, User.email == email))
    if existing and existing.deleted_at is None:
        raise HTTPException(409, 'Пользователь уже существует')
    if payload.manager_id:
        manager = await db.scalar(select(User).where(User.id == payload.manager_id, User.tenant_id == tenant_id, User.deleted_at.is_(None)))
        if not manager:
            raise HTTPException(422, 'manager_id не относится к текущему тенанту')
    new_user = existing or User(tenant_id=tenant_id, email=email)
    new_user.role = payload.role; new_user.manager_id = payload.manager_id; new_user.deleted_at = None
    db.add(new_user); await db.flush()
    settings = get_settings(); raw = secrets.token_urlsafe(32)
    db.add(MagicLinkToken(user_id=new_user.id, tenant_id=new_user.tenant_id, email=email, token_hash=token_hash(raw), purpose='invite', expires_at=utcnow() + timedelta(hours=settings.invite_ttl_hours)))
    await db.commit()
    url = f"{settings.app_base_url.rstrip('/')}/api/auth/verify?token={quote(raw)}"
    await send_magic_link(settings, email, url, 'invite')
    return user_out(new_user)


@router.get('/api/users')
async def list_users(ctx=Depends(current_context), db: AsyncSession = Depends(get_db)):
    user, tenant, _ = ctx; require_roles(user, {'owner', 'rop', 'analyst'})
    await set_tenant_scope(db, str(tenant.id))
    users = (await db.scalars(select(User).where(User.tenant_id == tenant.id, User.deleted_at.is_(None)).order_by(User.created_at))).all()
    return {'users': [user_out(item) for item in users]}


@router.patch('/api/users/{user_id}')
async def patch_user(user_id: UUID, payload: UserPatch, ctx=Depends(current_context), _csrf=Depends(csrf_guard), db: AsyncSession = Depends(get_db)):
    user, tenant, _ = ctx; require_roles(user, {'owner'})
    target = await db.scalar(select(User).where(User.id == user_id, User.tenant_id == tenant.id))
    if not target:
        raise HTTPException(404, 'Пользователь не найден')
    data = payload.model_dump(exclude_unset=True)
    if 'role' in data and data['role'] not in ROLES:
        raise HTTPException(422, 'Недопустимая роль')
    if 'manager_id' in data and data['manager_id']:
        manager = await db.scalar(select(User).where(User.id == data['manager_id'], User.tenant_id == tenant.id, User.deleted_at.is_(None)))
        if not manager: raise HTTPException(422, 'manager_id не относится к текущему тенанту')
    for key, value in data.items(): setattr(target, key, value)
    await db.commit()
    return user_out(target)
