from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from bekstyle.api.schemas import SettingsOut
from bekstyle.db import get_db, get_setting

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("", response_model=SettingsOut)
async def get_public_settings(db: AsyncSession = Depends(get_db)):
    contact = await get_setting(db, "contact_username") or "bekstyle_admin"
    yuan = await get_setting(db, "yuan_rate") or "1850"
    markup = await get_setting(db, "markup_percent") or "35"
    delivery = await get_setting(db, "delivery_text") or "10-18 kun ichida O'zbekiston bo'ylab yetkaziladi"
    channel = await get_setting(db, "channel_username") or "bekstyle_uz"

    return SettingsOut(
        contact_username=contact,
        yuan_rate=int(yuan) if yuan.isdigit() else 1850,
        markup_percent=int(markup) if markup.isdigit() else 35,
        delivery_text=delivery,
        channel_username=channel,
    )
