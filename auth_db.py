from collections.abc import AsyncIterator
from sqlalchemy import text
from sqlalchemy.pool import NullPool
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from auth_models import Base
from auth_settings import get_settings


settings = get_settings()
engine = create_async_engine(settings.database_url, pool_pre_ping=True, poolclass=NullPool)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session


async def set_tenant_scope(session: AsyncSession, tenant_id: str) -> None:
    """Enable PostgreSQL RLS scope; SQLite uses explicit tenant_id predicates in routes."""
    if session.bind and session.bind.dialect.name == 'postgresql':
        safe = str(tenant_id).replace("'", "''")
        await session.execute(text(f"SET LOCAL app.current_tenant = '{safe}'"))
