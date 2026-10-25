from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from bekstyle.api.auth import TelegramUser, get_current_user
from bekstyle.api.schemas import UserProfileOut, format_som
from bekstyle.db import Order, User, get_db

router = APIRouter(prefix="/user", tags=["user"])


@router.get("/profile", response_model=UserProfileOut)
@router.get("/me", response_model=UserProfileOut)
async def get_user_profile(
    user: TelegramUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Ensure user exists in db
    u = await db.get(User, user.id)
    if not u:
        u = User(
            telegram_id=user.id,
            name=f"{user.first_name} {user.last_name or ''}".strip(),
            username=user.username,
            balance=0,
        )
        db.add(u)
        await db.commit()
        await db.refresh(u)

    orders_count = (
        await db.execute(select(func.count(Order.id)).where(Order.user_id == user.id))
    ).scalar() or 0

    last_order = (
        await db.execute(
            select(Order).where(Order.user_id == user.id).order_by(Order.id.desc()).limit(1)
        )
    ).scalar_one_or_none()

    return UserProfileOut(
        telegram_id=u.telegram_id,
        name=u.name or user.first_name,
        username=u.username,
        phone=u.phone or (last_order.phone if last_order else None),
        saved_city=last_order.city if last_order else "",
        saved_address=last_order.address if last_order else "",
        orders_count=orders_count,
        is_admin=user.is_admin,
    )


@router.post("/sync", response_model=UserProfileOut)
async def sync_user(
    user: TelegramUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await get_user_profile(user=user, db=db)
    return await get_user_profile(user, db)
