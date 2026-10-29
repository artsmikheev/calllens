# Module 1: Auth + Tenants — отчёт

## Статус

Module 1 реализован поверх существующего FastAPI MVP CallLens. Scoring, транскрибация, dashboard, CRM и `/api/analyze` не переписывались.

В текущей среде PostgreSQL 15 не был доступен, поэтому локальная проверка выполнена на SQLite через `sqlite+aiosqlite`. Код и Alembic migration подготовлены для PostgreSQL с RLS.

## Изменённые / созданные файлы

### Auth runtime

- `auth_settings.py` — Pydantic Settings и `.env`-конфигурация.
- `auth_models.py` — SQLAlchemy 2 models: `Tenant`, `User`, `MagicLinkToken`, `Session`.
- `auth_db.py` — async engine, `AsyncSession`, database dependency и PostgreSQL tenant scope.
- `auth_mail.py` — `fastapi-mail` SMTP adapter и dev logging.
- `auth_routes.py` — magic links, sessions, logout, `/me`, invites, users и RBAC.
- `login.html` — минимальная страница входа.
- `app-home.html` — минимальная заглушка кабинета.
- `backend.py` — подключён auth router, добавлены auth assets, CORS переведён на `ALLOWED_ORIGINS`.

### Database / migrations

- `alembic.ini`;
- `alembic/env.py`;
- `alembic/versions/0001_auth_tenants.py`;
- `alembic/README`;
- `scripts/create_tenant.py`;
- `scripts/__init__.py`.

### Configuration / dependencies

- `requirements.txt` — SQLAlchemy async, Alembic, asyncpg, aiosqlite, pydantic-settings, fastapi-mail, httpx, pytest.
- `.env.example` — database, email, cookie, origins и TTL параметры.
- `pytest.ini` — async pytest configuration.

### Tests

- `tests/test_auth.py` — magic-link, token reuse/expiry, sessions, logout, RBAC, tenant isolation, rate limiting.

## Database schema

Migration создаёт:

- `tenants`;
- `users`;
- `magic_link_tokens`;
- `sessions` (включая `tenant_id`, чтобы установить RLS scope до чтения пользователя по session cookie).

Для PostgreSQL migration дополнительно:

- создаёт `pgcrypto` и `citext`;
- включает RLS на `users`;
- создаёт policy `users_tenant_isolation` через `current_setting('app.current_tenant', true)::uuid`.

Raw magic-link и session tokens в БД не сохраняются. Сохраняются только SHA-256 hashes.

## Реализованные endpoints

- `POST /api/auth/request-link`
  - всегда возвращает `202`;
  - неизвестный email не раскрывается;
  - TTL login token — 15 минут;
  - rate limit — 5 запросов в минуту на IP.
- `GET /api/auth/verify?token=...`
  - одноразовый token;
  - создаёт session на 30 дней;
  - ставит HttpOnly cookie;
  - в HTTP dev-режиме `Secure=False`;
  - redirect на `/app`.
- `POST /api/auth/logout`
  - отзывает session;
  - очищает cookie.
- `GET /api/auth/me`
  - возвращает user и tenant;
  - 401 без активной cookie.
- `POST /api/tenants/{tenant_id}/invite`
  - owner может приглашать любые роли;
  - rop может приглашать только manager;
  - invite token TTL — 72 часа.
- `GET /api/users`
  - доступен owner, rop, analyst;
  - manager получает 403.
- `PATCH /api/users/{user_id}`
  - доступен только owner;
  - разрешены role, manager_id, full_name, deleted_at.

Страницы:

- `/login` — magic-link login;
- `/app` — минимальная auth-заглушка с `/api/auth/me` и logout.

## RBAC

| Действие | owner | rop | manager | analyst |
|---|---:|---:|---:|---:|
| Приглашать | да | да, только manager | нет | нет |
| Менять роли | да | нет | нет | нет |
| Список пользователей | да | да | нет | да |
| `/api/auth/me`, logout | да | да | да | да |

## Tenant isolation

В SQLite fallback каждый запрос к `users` содержит явный `WHERE User.tenant_id == current_tenant`.

В PostgreSQL dependency `set_tenant_scope()` выполняет:

```sql
SET LOCAL app.current_tenant = '<tenant uuid>';
```

RLS включается migration-ом без изменения прикладных запросов.

## Пройденные тесты

- `python3 -m py_compile` для backend и всех auth-модулей — **passed**.
- `node --check app.js` — **passed**.
- `pytest -v tests/test_auth.py` — **11 passed на PostgreSQL**, **10 passed + 1 skipped на SQLite**.
- `alembic upgrade head` на SQLite — **passed**.
- `scripts/create_tenant.py` на SQLite — **passed**.
- Проверка таблиц tenants/users/tokens/sessions — **passed**.
- Основной frontend smoke test — **passed**.
- Dashboard smoke test — **passed**.
- Existing demo upload → result flow — **passed**.
- `/api/health`, `/login`, `/app` через FastAPI server — **passed**.

Остались только стандартные deprecation warnings HTTPX о передаче cookies на уровне запроса в тестах; они не влияют на результат.

## Как запустить локально

```bash
cd /home/ubuntu/sales-call-quality-app
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Для SQLite fallback:

```bash
export DATABASE_URL=sqlite+aiosqlite:///./calllens_auth.db
export APP_BASE_URL=http://localhost:8000
export EMAIL_MODE=log
export ALLOWED_ORIGINS=http://localhost:8000

alembic upgrade head
python3 scripts/create_tenant.py \
  --name "Pilot" \
  --slug pilot \
  --owner-email owner@example.com

uvicorn backend:app --host 0.0.0.0 --port 8000
```

Magic link в `EMAIL_MODE=log` пишется в лог backend. Это единственный режим, в котором raw link намеренно появляется в логах, исключительно для dev-тестирования.

Для PostgreSQL:

```bash
export DATABASE_URL=postgresql+asyncpg://user:password@host:5432/calllens
alembic upgrade head
```

## Известные ограничения

1. RLS проверен на PostgreSQL 16.15; PostgreSQL 15 не был доступен в apt-репозитории текущей sandbox-среды.
2. `users` получает RLS policy; для будущих tenant-таблиц нужно добавлять аналогичные policies.
3. Auth middleware пока защищает auth/tenant/user endpoints через dependencies, но не закрывает существующий `/api/analyze`, чтобы не ломать текущий MVP-контракт. Перед multi-tenant сохранением анализов `/api/analyze` необходимо привязать к current tenant.
4. `login.html` и `app-home.html` — минимальные страницы Module 1, не полноценный кабинет.
5. Rate limiter in-memory и не подходит для нескольких worker-процессов; для production нужен Redis или другой shared limiter.
6. Email SMTP не тестировался с реальным сервером; dev logging проверен через monkeypatch и локальный режим.
7. Tenant создаётся только через `scripts/create_tenant.py`; self-service регистрации нет.
8. В production необходимо оставить whitelist `ALLOWED_ORIGINS`, не возвращаться к `allow_origins=['*']`.

## Что нужно от заказчика перед Module 2

- подтвердить реальный PostgreSQL 15+ и способ подключения;
- подтвердить домен приложения и `APP_BASE_URL`;
- подтвердить SMTP-провайдера или разрешить dev-only logging;
- подтвердить список ролей и допустимые transitions;
- определить, какие сущности CallLens будут tenant-owned в Module 2: calls, transcripts, reports, checklists;
- определить retention policy для аудио, транскриптов и отчётов;
- решить, должен ли `/api/analyze` требовать авторизацию уже в Module 2;
- определить, нужна ли Redis-инфраструктура для rate limiting и фоновых задач.

## Security checklist

- [x] Raw tokens не сохраняются в БД.
- [x] Login token одноразовый и имеет TTL.
- [x] Session token хранится в HttpOnly cookie.
- [x] SameSite=Lax.
- [x] Secure включается при HTTPS `APP_BASE_URL`.
- [x] Enumeration protection для request-link.
- [x] Role checks для invite/users.
- [x] Explicit tenant filters для SQLite.
- [x] PostgreSQL RLS policy в migration.
- [x] Wildcard CORS заменён на `ALLOWED_ORIGINS`.
- [ ] Production PostgreSQL RLS execution test.
- [ ] Redis/shared rate limiter.
- [ ] Authenticated tenant scope для `/api/analyze`.
