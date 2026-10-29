import argparse
import asyncio
from auth_db import SessionLocal, init_db
from auth_models import Tenant, User
from sqlalchemy import select


async def main(name: str, slug: str, email: str):
    await init_db()
    async with SessionLocal() as db:
        existing = await db.scalar(select(Tenant).where(Tenant.slug == slug))
        if existing:
            raise SystemExit(f'Tenant already exists: {slug}')
        tenant = Tenant(name=name, slug=slug, plan='pilot')
        db.add(tenant)
        await db.flush()
        user = User(tenant_id=tenant.id, email=email.strip().lower(), role='owner')
        db.add(user)
        await db.commit()
        print(f'tenant_id={tenant.id}')
        print(f'user_id={user.id}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--name', required=True)
    parser.add_argument('--slug', required=True)
    parser.add_argument('--owner-email', required=True)
    args = parser.parse_args()
    asyncio.run(main(args.name, args.slug, args.owner_email))
