import os
from typing import Optional, Any
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    BOT_TOKEN: str = Field(
        default="9277851759:AAHjlbBoYpim8N5Xg-GCVodWaYU8Kxhq1VA",
        description="Telegram Bot API Token from @BotFather"
    )
    OWNER_SETUP_CODE: str = Field(
        default="moonlight_owner_secret_998877_setup",
        description="One-time secret token for claiming shop ownership"
    )
    WEBAPP_URL: str = Field(
        default="http://localhost:8001",
        description="Base URL where the Mini App is served"
    )
    BOT_POLLING_ENABLED: bool = Field(
        default=True,
        description="Disable on local API previews; use a separate bot token for local bot tests",
    )
    DATABASE_URL: str = Field(
        default="sqlite+aiosqlite:///./moonlight_shop.db",
        description="SQLAlchemy async database URL"
    )
    DEV_ADMIN_ID: Optional[int] = Field(
        default=None,
        description="Optional developer Telegram user ID for local testing"
    )
    DEV_BROWSER_MODE: bool = Field(
        default=False,
        description="Local only: accept the fake 'dev_browser_mode' initData as owner. Never enable in production."
    )
    HOST: str = Field(default="0.0.0.0")
    PORT: int = Field(default=8001)
    MEDIA_CACHE_DIR: str = Field(default="./media_cache")

    @field_validator("DEV_ADMIN_ID", mode="before")
    @classmethod
    def parse_empty_str_to_none(cls, v: Any) -> Optional[int]:
        if v == "" or v is None:
            return None
        return int(v)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
