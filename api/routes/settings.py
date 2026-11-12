from typing import Dict, Any
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Setting
from db.session import get_db

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("", response_model=Dict[str, Any])
async def get_public_settings(db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Setting))
    rows = res.scalars().all()
    data = {s.key: s.value for s in rows}

    return {
        "cargo_rate": int(data.get("cargo_rate", 10000)),
        "cargo_rate_avto": int(data.get("cargo_rate_avto", 10000)),
        "cargo_rate_avia": int(data.get("cargo_rate_avia", 14000)),
        "delivery_days_avto": data.get("delivery_days_avto", "14–18 kun"),
        "delivery_days_avia": data.get("delivery_days_avia", "7–9 kun"),
        "delivery_days": data.get("delivery_days", "7–18 kun"),
        "delivery_scope": data.get("delivery_scope", "O'zbekiston bo'ylab"),
        "payment_terms": data.get("payment_terms", "100% oldindan to'lov"),
        "payment_card": data.get("payment_card", "9860 3501 4255 8658 (Humo, Ma'rufjonova Gulmira)"),
        "location": data.get("location", "Toshkent"),
        "contact_username": data.get("contact_username", "MOONLIGHT_ADMINNN"),
        "channel_url": data.get("channel_url", "https://t.me/moonlight_chinese_shop"),
        "has_linked_channel": bool(data.get("channel_id")),
        "welcome_text": data.get("welcome_text", "Moonlight Chinese Shop ga xush kelibsiz! 🌙"),
    }
