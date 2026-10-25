import re
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    BOT_TOKEN: str = Field(default="", description="BEK STYLE bot token from @BotFather")
    OWNER_SETUP_CODE: str = Field(default="", description="Secret for the one-time /start claim_<code> link")
    DATA_DIR: str = Field(default="./data", description="Data directory for generated visuals")
    DATABASE_URL: str = Field(default="sqlite+aiosqlite:///./data/bek_style.db")
    PORT: int = Field(default=8000, description="Port for web server on Render")
    WEBAPP_URL: str = Field(default="https://bek-style-shop.onrender.com", description="Public HTTPS URL for Mini App")
    DEV_BROWSER_MODE: bool = Field(default=False, description="Enable browser dev mode for local testing without Telegram")
    DEV_ADMIN_ID: int | None = Field(default=None, description="Optional developer admin Telegram ID")

    @field_validator("DATABASE_URL", mode="after")
    @classmethod
    def normalize_database_url(cls, v: str) -> str:
        if not v:
            return v
        if v.startswith("postgres://"):
            v = v.replace("postgres://", "postgresql+asyncpg://", 1)
        elif v.startswith("postgresql://") and not v.startswith("postgresql+asyncpg://"):
            v = v.replace("postgresql://", "postgresql+asyncpg://", 1)

        # asyncpg expects ssl=require, not sslmode=require
        if "sslmode=" in v:
            v = re.sub(r"sslmode=[^&]*", "ssl=require", v)
        elif "ssl=" not in v and "neon.tech" in v:
            sep = "&" if "?" in v else "?"
            v = f"{v}{sep}ssl=require"

        # remove channel_binding if present
        if "channel_binding=" in v:
            v = re.sub(r"[&?]channel_binding=[^&]*", "", v)

        return v

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
