import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select
from db.models import Setting, Admin, User

NEON_URL = "postgresql+asyncpg://neondb_owner:npg_0RQUbe9NFiks@ep-gentle-smoke-b5s3n2fa-pooler.c-7.us-east-2.aws.neon.tech/neondb?ssl=require"

async def update_database(url: str, label: str):
    print(f"Connecting to {label}...")
    try:
        engine = create_async_engine(url)
        session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with session_factory() as session:
            # 1. Update contact_username setting
            res_c = await session.execute(select(Setting).where(Setting.key == "contact_username"))
            setting = res_c.scalars().first()
            if setting:
                setting.value = "MOONLIGHT_ADMINNN"
            else:
                session.add(Setting(key="contact_username", value="MOONLIGHT_ADMINNN"))

            # 2. Update Gulmira opa in Admin table
            res_a = await session.execute(select(Admin).where(Admin.telegram_id == 8413799379))
            admin = res_a.scalars().first()
            if admin:
                admin.username = "MOONLIGHT_ADMINNN"
                print(f"[{label}] Updated Admin 8413799379 username to MOONLIGHT_ADMINNN")
            else:
                session.add(Admin(telegram_id=8413799379, name="💞Gulmira💞", username="MOONLIGHT_ADMINNN", role="owner"))
                print(f"[{label}] Added Admin 8413799379 with username MOONLIGHT_ADMINNN")

            # 3. Update Gulmira opa in User table if exists
            res_u = await session.execute(select(User).where(User.telegram_id == 8413799379))
            user = res_u.scalars().first()
            if user:
                user.username = "MOONLIGHT_ADMINNN"
                print(f"[{label}] Updated User 8413799379 username to MOONLIGHT_ADMINNN")

            await session.commit()
            print(f"[{label}] Successfully updated contact_username to MOONLIGHT_ADMINNN!")
        await engine.dispose()
    except Exception as e:
        print(f"[{label}] Error: {e}")

async def main():
    # Update Neon cloud DB
    await update_database(NEON_URL, "Neon Cloud DB")

    # Also try local Docker DB if running
    local_url = "postgresql+asyncpg://moonlight_user:moonlight_password_2026@localhost:5432/moonlight_db"
    try:
        await update_database(local_url, "Local Docker DB")
    except Exception as e:
        print("Local Docker DB skipped:", e)

if __name__ == "__main__":
    asyncio.run(main())
