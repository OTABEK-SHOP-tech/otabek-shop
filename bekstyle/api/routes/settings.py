from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from bekstyle.api.schemas import SettingsOut
from bekstyle.db import get_db, get_setting

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("", response_model=SettingsOut)
async def get_public_settings(db: AsyncSession = Depends(get_db)):
    contact = await get_setting(db, "contact_username") or "bekstyle_admin"
    delivery = await get_setting(db, "delivery_text") or "O'zbekiston bo'ylab tezkor yetkazib beriladi"
    channel = await get_setting(db, "channel_username") or "bek_style_shop"
    card1 = await get_setting(db, "payment_card_1") or "4916 9903 4816 9779"
    card2 = await get_setting(db, "payment_card_2") or "9860 2301 0748 6030"
    cargo = await get_setting(db, "cargo_info") or "Cargo haqi tortilgandan keyin alohida hisoblanadi"

    return SettingsOut(
        contact_username=contact,
        delivery_text=delivery,
        channel_username=channel,
        payment_card_1=card1,
        payment_card_2=card2,
        cargo_info=cargo,
    )
