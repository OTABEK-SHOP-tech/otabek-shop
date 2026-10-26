from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from bekstyle.api.schemas import SettingsOut
from bekstyle.db import DEFAULT_SETTINGS, get_db, get_setting, Admin, User

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("", response_model=SettingsOut)
async def get_public_settings(db: AsyncSession = Depends(get_db)):
    contact = (await get_setting(db, "contact_username") or "").strip().lstrip("@")
    if contact == "bekstyle_admin":
        # The inherited placeholder must never direct customers to an unrelated account.
        contact = await db.scalar(select(User.username).join(Admin, Admin.telegram_id == User.telegram_id).where(Admin.role == "owner")) or ""
    delivery = await get_setting(db, "delivery_text") or ""
    if delivery == "O'zbekiston bo'ylab tezkor yetkazib beriladi":
        delivery = "Yetkazish muddati buyurtma uchun alohida tasdiqlanadi."
    channel = (await get_setting(db, "channel_username") or "").strip().lstrip("@")
    if channel == "bek_style_shop":
        channel = ""
    card1 = await get_setting(db, "payment_card_1") or "4916 9903 4816 9779"
    card2 = await get_setting(db, "payment_card_2") or "9860 2301 0748 6030"
    cargo = await get_setting(db, "cargo_info") or "Cargo haqi tortilgandan keyin alohida hisoblanadi"
    cargo_carrier = await get_setting(db, "cargo_carrier") or DEFAULT_SETTINGS["cargo_carrier"]

    return SettingsOut(
        contact_username=contact,
        delivery_text=delivery,
        channel_username=channel,
        payment_card_1=card1,
        payment_card_2=card2,
        cargo_carrier=cargo_carrier,
        cargo_info=cargo,
    )
