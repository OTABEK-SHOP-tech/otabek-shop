import logging
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import get_current_user, TelegramUser, require_admin
from api.schemas import (
    ReferralStatsOut,
    CouponValidateRequest,
    CouponValidateResponse,
    ReferralCouponOut,
    ReferralInviteItem,
)
from bot.loader import bot
from bot.services.referral_service import (
    get_user_referral_stats,
    validate_and_calculate_coupon_discount,
)
from db.models import CartItem, Referral, ReferralCoupon, User
from db.session import get_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/referrals", tags=["referrals"])


@router.get("/me", response_model=ReferralStatsOut)
async def get_my_referrals_and_coupons(
    user: TelegramUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns full referral dashboard data for the authenticated customer:
    - Personal referral link
    - Number of verified friends joined
    - Next 20% coupon milestone progress
    - Earned, active, and used 20% discount coupons
    - List of recent invitees
    """
    bot_username = "moonlight_chinese_bot"
    if bot:
        try:
            bot_me = await bot.get_me()
            bot_username = bot_me.username
        except Exception:
            pass

    stats = await get_user_referral_stats(db, user.id, bot_username)
    return ReferralStatsOut(
        user_id=stats["user_id"],
        referral_link=stats["referral_link"],
        confirmed_count=stats["confirmed_count"],
        pending_count=stats["pending_count"],
        revoked_count=stats["revoked_count"],
        next_milestone=stats["next_milestone"],
        friends_needed_for_next=stats["friends_needed_for_next"],
        total_coupons_earned=stats["total_coupons_earned"],
        available_coupons=[ReferralCouponOut(**cp) for cp in stats["available_coupons"]],
        used_coupons=[ReferralCouponOut(**cp) for cp in stats["used_coupons"]],
        recent_invites=[ReferralInviteItem(**inv) for inv in stats["recent_invites"]],
    )


@router.post("/validate-coupon", response_model=CouponValidateResponse)
async def validate_referral_coupon(
    payload: CouponValidateRequest,
    user: TelegramUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Validates a referral coupon against the user's cart items,
    calculating a 20% discount on 1 unit of the chosen or highest-priced item.
    """
    # Query user's current cart items
    cart_res = await db.execute(select(CartItem).where(CartItem.user_id == user.id))
    cart_items = cart_res.scalars().all()

    if not cart_items:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Savat bo'sh. Kuponni qo'llash uchun avval savatga mahsulot qo'shing",
        )

    # Convert to format with price & title
    items_data = []
    for ci in cart_items:
        prod = ci.product
        if not prod:
            continue
        items_data.append({
            "product_id": prod.id,
            "title": prod.title,
            "price": prod.price,
            "qty": ci.qty,
        })

    val_res = await validate_and_calculate_coupon_discount(
        session=db,
        user_id=user.id,
        code=payload.code,
        cart_items=items_data,
        selected_product_id=payload.product_id,
    )

    if not val_res.get("valid"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=val_res.get("message", "Kupon yaroqsiz"),
        )

    return CouponValidateResponse(**val_res)


@router.get("/admin/summary")
async def get_admin_referral_summary(
    admin_user: TelegramUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Admin view of total referral system statistics."""
    total_refs = (await db.execute(select(func.count(Referral.id)))).scalar() or 0
    confirmed_refs = (await db.execute(select(func.count(Referral.id)).where(Referral.status == "confirmed"))).scalar() or 0
    total_coupons = (await db.execute(select(func.count(ReferralCoupon.id)))).scalar() or 0
    used_coupons = (await db.execute(select(func.count(ReferralCoupon.id)).where(ReferralCoupon.is_used == True))).scalar() or 0

    return {
        "total_referrals": total_refs,
        "confirmed_referrals": confirmed_refs,
        "total_coupons_issued": total_coupons,
        "used_coupons": used_coupons,
    }
