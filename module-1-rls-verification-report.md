# Module 1 — RLS, tests и проверка auth-кода

## A. PostgreSQL RLS

### Как поднят Postgres

Docker и `psql` изначально отсутствовали. Через apt установлен PostgreSQL 16.15 на локальный sandbox-хост. PostgreSQL 15 в доступном Ubuntu-репозитории не поставлялся, поэтому использована версия 16.15 как совместимая по проверяемым механизмам PostgreSQL RLS.

Созданы:

- база `calllens_test`;
- владелец migration/test: `calllens`;
- отдельная non-owner app-роль для RLS: `calllens_app`.

### Результат миграции

Команда:

```bash
DATABASE_URL=postgresql+asyncpg://calllens:calllens_test@127.0.0.1:5432/calllens_test \
  PYTHONPATH=. alembic upgrade head
```

Результат:

```text
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
INFO  [alembic.runtime.migration] Running upgrade  -> 0001_auth_tenants, auth and tenants with PostgreSQL RLS
```

Проверка таблицы `users` показала UUID, CITEXT, role check constraint и policy `users_tenant_isolation`. Состояние таблицы:

```text
 relrowsecurity | relforcerowsecurity
----------------+---------------------
 t              | f
```

`relrowsecurity=t` подтверждает включение RLS. `relforcerowsecurity=f` означает стандартное поведение PostgreSQL: владелец таблицы обходит RLS, поэтому ручная проверка выполнялась отдельной non-owner ролью `calllens_app`.

### Результат тестов на PostgreSQL

Команда:

```bash
DATABASE_URL=postgresql+asyncpg://calllens:calllens_test@127.0.0.1:5432/calllens_test \
DATABASE_URL_RLS=postgresql+asyncpg://calllens_app:calllens_app_test@127.0.0.1:5432/calllens_test \
PYTHONPATH=. pytest -v tests/test_auth.py
```

Результат: **11 passed**.

### Ручная проверка RLS

Созданы два tenant и два пользователя:

```text
Tenant One: 11111111-1111-1111-1111-111111111111
Tenant Two: 22222222-2222-2222-2222-222222222222
```

Пользователи:

```text
one@example.com — tenant 1
 two@example.com — tenant 2
```

При выполнении от non-owner роли `calllens_app`:

```sql
BEGIN;
SET LOCAL app.current_tenant = '11111111-1111-1111-1111-111111111111';
SELECT id, tenant_id, email FROM users ORDER BY email;
COMMIT;
```

Получен только пользователь tenant 1:

```text
                  id                  |              tenant_id               |      email
--------------------------------------+--------------------------------------+-----------------
 11111111-1111-1111-1111-111111111101 | 11111111-1111-1111-1111-111111111111 | one@example.com
(1 row)
```

Проверка после `RESET`:

```sql
RESET app.current_tenant;
SELECT id, tenant_id, email FROM users ORDER BY email;
```

Результат:

```text
ERROR: invalid input syntax for type uuid: ""
```

Это ожидаемое поведение именно для текущей policy: `current_setting(..., true)` возвращает пустую строку в данной сессии, а приведение пустой строки к UUID вызывает ошибку. Данных без tenant scope не возвращается.

Проверка вставки пользователя tenant 2 при установленном scope tenant 1:

```sql
BEGIN;
SET LOCAL app.current_tenant = '11111111-1111-1111-1111-111111111111';
INSERT INTO users (id,tenant_id,email,role)
VALUES ('33333333-3333-3333-3333-333333333333',
        '22222222-2222-2222-2222-222222222222',
        'forbidden@example.com','manager');
ROLLBACK;
```

Результат:

```text
ERROR: new row violates row-level security policy for table "users"
```

### Вывод по RLS

RLS на реальном PostgreSQL работает: tenant 1 видит только свои строки, отсутствие scope не возвращает строки, а вставка пользователя в чужой tenant запрещена. Для production app connection необходимо использовать отдельную non-owner роль, а не владельца таблиц.

Дополнительное исправление в коде: в `sessions` и `magic_link_tokens` хранится `tenant_id`, чтобы установить RLS scope до первого запроса к `users`. Это необходимо, поскольку PostgreSQL RLS не позволяет безопасно определить tenant через `users` до установки scope.

## B. Список тестов

### Полный вывод `pytest -v tests/test_auth.py` на PostgreSQL

```text
============================= test session starts ==============================
platform linux -- Python 3.12.3, pytest-9.2.0, pluggy-1.7.0 -- /usr/bin/python3
cachedir: .pytest_cache
rootdir: /home/ubuntu/sales-call-quality-app
configfile: pytest.ini
plugins: asyncio-1.4.1, anyio-4.15.1
asyncio: mode=Mode.AUTO, debug=False, asyncio_default_fixture_loop_scope=function, asyncio_default_test_loop_scope=function
collected 11 items

tests/test_auth.py::test_request_link_existing_user PASSED               [  9%]
tests/test_auth.py::test_request_link_unknown_email PASSED               [ 18%]
tests/test_auth.py::test_verify_valid_token PASSED                       [ 27%]
tests/test_auth.py::test_verify_expired_token PASSED                     [ 36%]
tests/test_auth.py::test_verify_reused_token PASSED                      [ 45%]
tests/test_auth.py::test_me_without_cookie PASSED                        [ 54%]
tests/test_auth.py::test_me_with_cookie PASSED                           [ 63%]
tests/test_auth.py::test_logout_revokes_session PASSED                   [ 72%]
tests/test_auth.py::test_tenant_isolation PASSED                         [ 81%]
tests/test_auth.py::test_tenant_isolation_direct_query PASSED            [ 90%]
tests/test_auth.py::test_request_link_rate_limit PASSED                  [100%]

======================== 11 passed, 5 warnings in 4.02s ========================
```

Warnings — только deprecation warnings HTTPX о передаче cookies на уровне конкретного request. На результат auth/RLS они не влияют.

### Соответствие исходным 10 тестам

Все 10 тестов из исходной спецификации реализованы отдельными test functions:

| Спецификация | Реализованный тест |
|---|---|
| `test_request_link_existing_user` | `test_request_link_existing_user` |
| `test_request_link_unknown_email` | `test_request_link_unknown_email` |
| `test_verify_valid_token` | `test_verify_valid_token` |
| `test_verify_expired_token` | `test_verify_expired_token` |
| `test_verify_reused_token` | `test_verify_reused_token` |
| `test_me_without_cookie` | `test_me_without_cookie` |
| `test_me_with_cookie` | `test_me_with_cookie` |
| `test_logout_revokes_session` | `test_logout_revokes_session` |
| `test_tenant_isolation` | `test_tenant_isolation` |
| `test_tenant_isolation_direct_query` | `test_tenant_isolation_direct_query` |

Добавлен один дополнительный тест сверх спецификации: `test_request_link_rate_limit`, потому что rate limiting является обязательным требованием API-контракта.

В SQLite `test_tenant_isolation_direct_query` получает `SKIPPED`, поскольку SQLite не поддерживает RLS. На PostgreSQL тест проходит через отдельную non-owner роль `DATABASE_URL_RLS`.

## C. Ключевой код

### Код verify

Файл: `sales-call-quality-app/auth_routes.py`, строки 143–160.

```python
@router.get('/api/auth/verify')
async def verify_link(token: str, request: Request, db: AsyncSession = Depends(get_db)):
    row = await db.scalar(
        select(MagicLinkToken).where(
            MagicLinkToken.token_hash == token_hash(token)
        )
    )
    if not row or row.used_at is not None or not as_aware(row.expires_at) or as_aware(row.expires_at) <= utcnow():
        return HTMLResponse(
            '<h1>Ссылка недействительна или истекла.</h1>'
            '<p><a href="/login">Запросить новую</a></p>',
            status_code=400
        )
    if row.user_id is None:
        return HTMLResponse(
            '<h1>Приглашение не связано с пользователем.</h1>'
            '<p><a href="/login">Перейти ко входу</a></p>',
            status_code=400
        )
    if row.tenant_id:
        await set_tenant_scope(db, str(row.tenant_id))
    user = await db.scalar(
        select(User).where(
            User.id == row.user_id,
            User.tenant_id == row.tenant_id,
            User.deleted_at.is_(None)
        )
    )
    if not user:
        return HTMLResponse(
            '<h1>Пользователь недоступен.</h1>'
            '<p><a href="/login">Перейти ко входу</a></p>',
            status_code=400
        )
    row.used_at = utcnow()
    raw_session = secrets.token_urlsafe(40)
    settings = get_settings()
    db.add(Session(
        user_id=user.id,
        tenant_id=user.tenant_id,
        token_hash=token_hash(raw_session),
        user_agent=request.headers.get('user-agent'),
        expires_at=utcnow() + timedelta(days=settings.session_ttl_days)
    ))
    user.last_login_at = utcnow()
    await db.commit()
    response = RedirectResponse('/app', status_code=302)
    response.set_cookie(
        settings.auth_cookie_name,
        raw_session,
        max_age=settings.session_ttl_days * 86400,
        httponly=True,
        secure=settings.cookie_secure,
        samesite='lax',
        path='/'
    )
    return response
```

### Dependency, читающая session cookie

В проекте функция называется не `get_current_user`, а `current_context`. Файл: `auth_routes.py`, строки 86–102.

```python
async def current_context(
    request: Request,
    db: AsyncSession = Depends(get_db),
    session_cookie: str | None = Cookie(default=None, alias='session')
) -> tuple[User, Tenant, Session]:
    if not session_cookie:
        raise HTTPException(401, 'Требуется вход')
    row = await db.scalar(
        select(Session).where(
            Session.token_hash == token_hash(session_cookie),
            Session.revoked_at.is_(None)
        )
    )
    if not row or not as_aware(row.expires_at) or as_aware(row.expires_at) <= utcnow():
        raise HTTPException(401, 'Сессия истекла или отозвана')
    await set_tenant_scope(db, str(row.tenant_id))
    user = await db.scalar(
        select(User).where(
            User.id == row.user_id,
            User.tenant_id == row.tenant_id,
            User.deleted_at.is_(None)
        )
    )
    if not user:
        raise HTTPException(401, 'Пользователь недоступен')
    await set_tenant_scope(db, str(user.tenant_id))
    tenant = await db.scalar(
        select(Tenant).where(
            Tenant.id == user.tenant_id,
            Tenant.deleted_at.is_(None)
        )
    )
    if not tenant:
        raise HTTPException(401, 'Тенант недоступен')
    request.state.current_user = user
    request.state.current_tenant = tenant
    return user, tenant, row
```

### Установка tenant scope

Файл: `auth_db.py`, строки 25–30.

```python
async def set_tenant_scope(session: AsyncSession, tenant_id: str) -> None:
    """Enable PostgreSQL RLS scope; SQLite uses explicit tenant_id predicates in routes."""
    if session.bind and session.bind.dialect.name == 'postgresql':
        safe = str(tenant_id).replace("'", "''")
        await session.execute(
            text(f"SET LOCAL app.current_tenant = '{safe}'")
        )
```

### Создание сессии при логине

Файл: `auth_routes.py`, строка 157.

```python
db.add(Session(
    user_id=user.id,
    tenant_id=user.tenant_id,
    token_hash=token_hash(raw_session),
    user_agent=request.headers.get('user-agent'),
    expires_at=utcnow() + timedelta(days=settings.session_ttl_days)
))
```

`tenant_id` берётся из `user.tenant_id`, который найден по одноразовому magic-link token. Клиентский запрос не передаёт tenant_id в verify.

### Подтверждение четырёх пунктов

1. **Tenant session берётся из user:** да. При создании session используется `tenant_id=user.tenant_id`.
2. **Session tenant сверяется с user tenant:** да. В `current_context` используется `User.tenant_id == row.tenant_id`.
3. **SET LOCAL выполняется до запроса users:** да. `current_context` устанавливает scope на строке 92 до запроса users на строке 93. `verify` устанавливает scope на строке 151 до запроса users на строке 152.
4. **Подделка cookie не даёт доступ к чужому tenant:** raw cookie превращается в SHA-256 hash и ищется в sessions; session tenant сверяется с user tenant; RLS дополнительно фильтрует users. Ручная вставка чужого tenant через non-owner role запрещена RLS.

## Итог

### Готов ли Module 1 к Module 2

**Да, по auth/RLS-фундаменту Module 1 можно считать готовым к Module 2.** Реальная PostgreSQL RLS-проверка проведена на PostgreSQL 16.15, migration применена, 11 auth tests прошли, ручная tenant isolation проверка прошла.

Перед использованием в production остаются обязательные hardening-задачи: запуск на PostgreSQL 15/16 production-кластере с non-owner app role, проверка `FORCE ROW LEVEL SECURITY` в соответствии с deployment policy, shared rate limiter, secrets management и интеграционные тесты через настоящий SMTP.

### Оставшиеся риски

1. Проверка выполнена на PostgreSQL 16.15, а не 15.x, потому что PostgreSQL 15 не был доступен в apt-репозитории текущего Ubuntu-окружения.
2. В production нельзя использовать владельца таблиц как application role, иначе owner может обходить RLS.
3. `RESET app.current_tenant` сейчас даёт PostgreSQL error из-за приведения пустой строки к UUID; это безопаснее, чем вернуть строки, но при желании можно изменить policy на более явное no-row поведение.
4. `DATABASE_URL_RLS` используется отдельным тестом для non-owner RLS direct query.
5. Existing `/api/analyze` пока не защищён auth dependency, чтобы сохранить Module 0 MVP-контракт; перед tenant-owned calls/reports это нужно сделать в Module 2.
6. Rate limiter пока in-memory и не рассчитан на несколько worker-процессов.
7. UI `/login` и `/app` остаются минимальными заглушками Module 1.
