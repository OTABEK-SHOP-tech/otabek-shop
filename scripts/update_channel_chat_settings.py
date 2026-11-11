import asyncio
import os
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

NEON_URL = "postgresql+asyncpg://neondb_owner:npg_0RQUbe9NFiks@ep-gentle-smoke-b5s3n2fa-pooler.c-7.us-east-2.aws.neon.tech/neondb?ssl=require"


async def main():
    engine = create_async_engine(NEON_URL)
    async with engine.begin() as conn:
        for k, v in [
            ("channel_id", "-1004378811161"),
            ("channel_url", "https://t.me/moonlight_chinese_shop"),
            ("chat_id", "-1003565030513"),
            ("chat_url", "https://t.me/MY_interesno"),
        ]:
            await conn.execute(
                text("""
                    INSERT INTO settings (key, value) VALUES (:k, :v)
                    ON CONFLICT (key) DO UPDATE SET value = :v
                """),
                {"k": k, "v": v}
            )
    print("Neon settings updated!")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
