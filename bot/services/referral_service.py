from html import escape
import logging
import random
import string
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy import select, update, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError

from api.config import settings
from db.models import Referral, ReferralCoupon, PromoCode, User, Setting, Contest, ContestReferral, utcnow

logger = logging.getLogger(__name__)

# In-memory throttle for Tasdiqlash button: invitee_id -> timestamp
_confirm_throttle: Dict[int, float] = {}


def _ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """Ensures naive datetimes from SQLite/legacy rows are treated as UTC."""
    if dt is None:
        return None
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def get_user_referral_link(bot_username: str, user_id: int) -> str:
    """Generates the unique deep link for inviting friends."""
    clean_bot = bot_username.lstrip("@")
    return f"https://t.me/{clean_bot}?start=ref_{user_id}"


async def generate_unique_coupon_code(session: AsyncSession) -> str:
    """
    Generates a unique coupon code in the format REF20-XXXX-XXXX.
    Ensures uniqueness in ReferralCoupon table.
    """
    chars = string.ascii_uppercase + string.digits
    for _ in range(50):
        part1 = "".join(random.choices(chars, k=4))
        part2 = "".join(random.choices(chars, k=4))
        code = f"REF20-{part1}-{part2}"
        res = await session.execute(select(ReferralCoupon).where(ReferralCoupon.code == code))
        if not res.scalars().first():
            return code
    # Fallback timestamp-based code
    return f"REF20-{int(datetime.now().timestamp())}"


async def get_channel_info(session: AsyncSession) -> Tuple[Optional[str], str]:
    """Retrieves channel_id and channel_url from settings."""
    res_id = await session.execute(select(Setting).where(Setting.key == "channel_id"))
    ch_id_rec = res_id.scalars().first()
    channel_id = ch_id_rec.value.strip() if ch_id_rec and ch_id_rec.value.strip() else None

    res_url = await session.execute(select(Setting).where(Setting.key == "channel_url"))
    ch_url_rec = res_url.scalars().first()
    channel_url = ch_url_rec.value.strip() if ch_url_rec and ch_url_rec.value.strip() else "https://t.me/moonlight_chinese_shop"

    return channel_id, channel_url


async def process_referral_start(
    session: AsyncSession,
    bot: Optional[Bot],
    invitee_id: int,
    invitee_full_name: str,
    invitee_username: Optional[str],
    is_bot: bool,
    referrer_id: int,
    is_new_user: bool,
) -> Dict[str, Any]:
    """
    Handles when a user opens an invitation link: /start ref_<referrer_id>.
    Strict verification:
    - No self-referrals
    - No bots
    - Referrer must exist
    - Existing bot users cannot be invited for referral points
    - Honest check if invitee was already in channel
    """
    if is_bot or invitee_id == referrer_id:
        return {"valid": False, "reason": "self_or_bot"}

    # Referrer must exist in DB
    ref_user_res = await session.execute(select(User).where(User.telegram_id == referrer_id))
    referrer_user = ref_user_res.scalars().first()
    if not referrer_user:
        return {"valid": False, "reason": "invalid_referrer"}

    # Check if referral already recorded for this invitee
    existing_ref_res = await session.execute(
        select(Referral).where(Referral.invitee_id == invitee_id)
    )
    existing_ref = existing_ref_res.scalars().first()
    if existing_ref:
        channel_id, channel_url = await get_channel_info(session)
        # If this is the same referrer, return valid so user can see confirm button / status
        if existing_ref.referrer_id == referrer_id:
            return {
                "valid": True,
                "already_registered": True,
                "referral": existing_ref,
                "channel_url": channel_url,
                "was_member_before": existing_ref.was_member_before,
            }
        else:
            return {
                "valid": False,
                "reason": "already_referred_by_other",
                "message": "Siz allaqachon boshqa do'stingiz taklifi bilan ro'yxatdan o'tgansiz 🌸",
            }

    # Existing bot user check (only applies if user has never been referred before)
    if not is_new_user:
        return {
            "valid": False,
            "reason": "existing_user",
            "message": (
                "🌸 <b>Siz avval ham botimizdan foydalangansiz</b> 🎀\n\n"
                "Do'stingizga taklif balli hisoblanmaydi, lekin siz ham o'z do'stlaringizni taklif qilib, "
                "har <b>5 ta do'stingiz uchun 20% CHEGIRMA</b> kuponiga ega bo'lishingiz mumkin! 🎁"
            ),
        }

    # Check if invitee was already a member of the channel before clicking link
    channel_id, channel_url = await get_channel_info(session)
    was_member_before = False
    if channel_id and bot:
        try:
            member = await bot.get_chat_member(chat_id=channel_id, user_id=invitee_id)
            if member.status in ("creator", "administrator", "member"):
                was_member_before = True
            elif member.status == "restricted" and getattr(member, "is_member", True):
                was_member_before = True
        except Exception as e:
            logger.warning(f"Could not check membership for {invitee_id} in {channel_id}: {e}")

    # Create pending/disqualified referral record
    new_referral = Referral(
        referrer_id=referrer_id,
        invitee_id=invitee_id,
        status="was_member_before" if was_member_before else "pending",
        was_member_before=was_member_before,
        created_at=utcnow(),
    )
    session.add(new_referral)

    # If there is also an active contest, create pending contest referral for bonus synergy
    try:
        active_contest_res = await session.execute(
            select(Contest).where(Contest.status == "active").order_by(Contest.created_at.desc())
        )
        active_c = active_contest_res.scalars().first()
        if active_c and _ensure_utc(active_c.ends_at) > utcnow():
            c_ref_res = await session.execute(
                select(ContestReferral).where(
                    ContestReferral.contest_id == active_c.id,
                    ContestReferral.invitee_id == invitee_id,
                )
            )
            if not c_ref_res.scalars().first():
                session.add(
                    ContestReferral(
                        contest_id=active_c.id,
                        invitee_id=invitee_id,
                        referrer_id=referrer_id,
                        status="pending",
                        was_member_before=was_member_before,
                        started_at=utcnow(),
                    )
                )
    except Exception as e:
        logger.warning(f"Error mirroring referral to contest: {e}")

    await session.commit()

    return {
        "valid": True,
        "already_registered": False,
        "referral": new_referral,
        "channel_url": channel_url,
        "was_member_before": was_member_before,
    }


async def confirm_referral(
    session: AsyncSession,
    bot: Optional[Bot],
    invitee_id: int,
    referrer_id: int,
    bot_username: str,
    bypass_throttle: bool = False,
) -> Dict[str, Any]:
    """
    Invitee clicked ✅ Tasdiqlash button (or joined channel directly via chat_member).
    Verifies channel membership with Telegram API, transitions status to 'confirmed',
    checks 5-friends milestones (5, 10, 15, ...), mints 20% discount coupons,
    and notifies referrer.
    """
    # Query referral record first so already-confirmed auto-joins don't hit throttle
    ref_res = await session.execute(
        select(Referral).where(Referral.invitee_id == invitee_id)
    )
    referral = ref_res.scalars().first()
    if not referral:
        if not bypass_throttle:
            now_ts = datetime.now().timestamp()
            last_ts = _confirm_throttle.get(invitee_id, 0.0)
            if now_ts - last_ts < 3.0:
                return {
                    "status": "throttled",
                    "message": "Iltimos, 3 soniya kuting ⏳",
                }
            _confirm_throttle[invitee_id] = now_ts
        return {
            "status": "not_found",
            "message": "Taklif ma'lumoti topilmadi 🌸",
        }

    personal_link = get_user_referral_link(bot_username, invitee_id)

    if referral.status == "confirmed":
        return {
            "status": "success",
            "message": "Obuna muvaffaqiyatli tasdiqlandi! 🌸",
            "personal_link": personal_link,
            "is_newly_confirmed": False,
        }

    if not bypass_throttle:
        now_ts = datetime.now().timestamp()
        last_ts = _confirm_throttle.get(invitee_id, 0.0)
        if now_ts - last_ts < 3.0:
            return {
                "status": "throttled",
                "message": "Iltimos, 3 soniya kuting ⏳",
            }
        _confirm_throttle[invitee_id] = now_ts

    channel_id, channel_url = await get_channel_info(session)
    if not channel_id:
        return {
            "status": "error",
            "message": "Kanal ulanmagan, iltimos adminga xabar bering 💌",
        }

    # Verify channel membership
    is_subscribed = False
    if bot:
        try:
            member = await bot.get_chat_member(chat_id=channel_id, user_id=invitee_id)
            if member.status in ("creator", "administrator", "member"):
                is_subscribed = True
            elif member.status == "restricted" and getattr(member, "is_member", True):
                is_subscribed = True
        except Exception as e:
            logger.warning(f"get_chat_member failed for user {invitee_id}: {e}")

    if not is_subscribed:
        return {
            "status": "not_subscribed",
            "message": "Siz hali kanalga obuna bo'lmadingiz 🙈",
            "channel_url": channel_url,
        }

    # If invitee was already in channel before, no point is awarded (honest accounting)
    if referral.was_member_before:
        if referral.status != "was_member_before":
            referral.status = "was_member_before"
            await session.commit()
        return {
            "status": "was_member_before",
            "message": (
                "Siz avvaldan kanal a'zosi bo'lganingiz sababli do'stingizga ball hisoblanmadi 🌸\n\n"
                "Lekin siz ham o'z do'stlaringizni taklif qilib, har 5 ta do'stingiz uchun "
                "<b>20% CHEGIRMA</b> kuponlarini yutib olishingiz mumkin! 🎁"
            ),
            "personal_link": personal_link,
        }

    # Transition status: pending/revoked -> confirmed
    now = utcnow()
    stmt = (
        update(Referral)
        .where(
            Referral.invitee_id == invitee_id,
            Referral.status.in_(["pending", "revoked"]),
        )
        .values(status="confirmed", confirmed_at=now, revoked_at=None)
    )
    res = await session.execute(stmt)
    is_newly_confirmed = res.rowcount > 0

    # Also mirror confirm in ContestReferral if active contest exists
    try:
        active_c_res = await session.execute(
            select(Contest).where(Contest.status == "active").order_by(Contest.created_at.desc())
        )
        active_c = active_c_res.scalars().first()
        if active_c and _ensure_utc(active_c.ends_at) > utcnow():
            await session.execute(
                update(ContestReferral)
                .where(
                    ContestReferral.contest_id == active_c.id,
                    ContestReferral.invitee_id == invitee_id,
                    ContestReferral.status.in_(["pending", "revoked"]),
                )
                .values(status="confirmed", confirmed_at=now, revoked_at=None)
            )
    except Exception as e:
        logger.warning(f"Error mirroring contest referral confirmation: {e}")

    await session.commit()

    if is_newly_confirmed:
        # Calculate total confirmed referrals for referrer
        cnt_res = await session.execute(
            select(func.count(Referral.id)).where(
                Referral.referrer_id == referral.referrer_id,
                Referral.status == "confirmed",
            )
        )
        confirmed_count = cnt_res.scalar() or 0

        # Reactivate any previously locked un-used coupons whose milestone is now reached again
        reactivate_res = await session.execute(
            select(ReferralCoupon).where(
                ReferralCoupon.user_id == referral.referrer_id,
                ReferralCoupon.is_used == False,
                ReferralCoupon.milestone <= confirmed_count,
            )
        )
        reactivate_coupons = reactivate_res.scalars().all()
        reactivate_codes = [c.code for c in reactivate_coupons]
        if reactivate_codes:
            await session.execute(
                update(PromoCode)
                .where(PromoCode.code.in_(reactivate_codes))
                .values(is_active=True)
            )

        # Check and grant 20% discount coupons for each 5-referrals milestone
        newly_earned_coupons: List[ReferralCoupon] = []
        for milestone in range(5, confirmed_count + 1, 5):
            # Check if coupon already minted for this user and milestone
            c_res = await session.execute(
                select(ReferralCoupon).where(
                    ReferralCoupon.user_id == referral.referrer_id,
                    ReferralCoupon.milestone == milestone,
                )
            )
            existing_coupon = c_res.scalars().first()
            if not existing_coupon:
                coupon_code = await generate_unique_coupon_code(session)
                new_coupon = ReferralCoupon(
                    user_id=referral.referrer_id,
                    code=coupon_code,
                    discount_percent=20,
                    milestone=milestone,
                    is_used=False,
                    created_at=now,
                )
                session.add(new_coupon)

                # Also insert into PromoCode table for cross-compatibility
                promo = PromoCode(
                    code=coupon_code,
                    discount_percent=20,
                    min_order_amount=0,
                    max_uses=1,
                    used_count=0,
                    is_active=True,
                    valid_from=now,
                )
                session.add(promo)
                newly_earned_coupons.append(new_coupon)

        await session.commit()

        # Send Telegram notification to referrer
        if bot:
            try:
                invitee_res = await session.execute(select(User).where(User.telegram_id == invitee_id))
                invitee_user = invitee_res.scalars().first()
                name_str = invitee_user.name if invitee_user and invitee_user.name else f"ID: {invitee_id}"

                # Base notification for the new member
                msg_lines = [
                    f"🎉 <b>+1 do'st qo'shildi!</b> {escape(str(name_str))} kanalga obuna bo'ldi 🌸",
                    f"📊 Jami taklif qilgan do'stlaringiz: <b>{confirmed_count} ta</b>",
                ]

                # If coupons were newly awarded
                if newly_earned_coupons:
                    for c in newly_earned_coupons:
                        msg_lines.append(
                            f"\n🥳 <b>TABRIKLAYMIZ! {c.milestone} ta do'st taklif qildingiz!</b>\n"
                            f"Sizga bitta hohlagan tovaringizga <b>20% CHEGIRMA</b> kuponi berildi! 🎟\n"
                            f"Kupon kodi: <code>{c.code}</code>\n"
                            f"<i>(Ushbu kuponni savatda buyurtma berishda ishlatishingiz mumkin)</i>"
                        )
                else:
                    used_ms_res = await session.execute(
                        select(ReferralCoupon.milestone).where(
                            ReferralCoupon.user_id == referral.referrer_id,
                            ReferralCoupon.is_used == True,
                        )
                    )
                    used_milestones = {m for m in used_ms_res.scalars().all()}
                    next_m = ((confirmed_count // 5) + 1) * 5
                    while next_m in used_milestones:
                        next_m += 5
                    needed = max(0, next_m - confirmed_count)
                    msg_lines.append(f"⏳ Keyingi 20% chegirma kuponigacha: <b>{needed} ta do'st</b> qoldi! ✨")

                await bot.send_message(
                    chat_id=referral.referrer_id,
                    text="\n".join(msg_lines),
                )
            except TelegramForbiddenError:
                logger.info(f"Referrer {referral.referrer_id} blocked bot.")
            except Exception as e:
                logger.warning(f"Could not notify referrer {referral.referrer_id}: {e}")

    return {
        "status": "success",
        "message": "Obuna muvaffaqiyatli tasdiqlandi! 🌸",
        "personal_link": personal_link,
        "is_newly_confirmed": is_newly_confirmed,
    }


async def revoke_referral_on_channel_leave(
    session: AsyncSession,
    bot: Optional[Bot],
    invitee_id: int,
) -> Optional[int]:
    """
    Called when an invitee leaves the channel.
    Revokes the confirmed referral point honestly and notifies the referrer.
    """
    res = await session.execute(
        select(Referral).where(
            Referral.invitee_id == invitee_id,
            Referral.status == "confirmed",
        )
    )
    referral = res.scalars().first()
    if not referral:
        return None

    referral.status = "revoked"
    referral.revoked_at = utcnow()
    await session.commit()

    # Get updated confirmed count
    cnt_res = await session.execute(
        select(func.count(Referral.id)).where(
            Referral.referrer_id == referral.referrer_id,
            Referral.status == "confirmed",
        )
    )
    new_count = cnt_res.scalar() or 0

    # Deactivate / lock any un-used coupons whose milestone is no longer met
    locked_res = await session.execute(
        select(ReferralCoupon).where(
            ReferralCoupon.user_id == referral.referrer_id,
            ReferralCoupon.is_used == False,
            ReferralCoupon.milestone > new_count,
        )
    )
    locked_coupons = locked_res.scalars().all()
    locked_codes = [c.code for c in locked_coupons]
    if locked_codes:
        await session.execute(
            update(PromoCode)
            .where(PromoCode.code.in_(locked_codes))
            .values(is_active=False)
        )
        await session.commit()

    if bot:
        try:
            msg_text = (
                f"⚠️ <b>Taklif qilgan do'stingiz kanaldan chiqib ketdi</b> 💔\n"
                f"Taklif ballingiz 1 taga kamaytirildi.\n"
                f"Hozirda faol takliflaringiz: <b>{new_count} ta</b>"
            )
            if locked_codes:
                msg_text += (
                    f"\n\n🔒 <b>Eslatma:</b> Faol do'stlaringiz soni kamaygani sababli "
                    f"20% chegirma kuponingiz vaqtincha bloklandi. "
                    f"Yangi do'st qo'shilsa, kupon avtomatik qayta faollashadi! ✨"
                )
            await bot.send_message(
                chat_id=referral.referrer_id,
                text=msg_text,
            )
        except Exception:
            pass

    return new_count


async def get_user_referral_stats(
    session: AsyncSession,
    user_id: int,
    bot_username: str,
) -> Dict[str, Any]:
    """
    Returns full referral dashboard stats for a user:
    - invite link
    - verified friend counts
    - next coupon milestone
    - available and used 20% discount coupons
    - recent invites list
    """
    ref_link = get_user_referral_link(bot_username, user_id)

    # Counts
    c_res = await session.execute(
        select(func.count(Referral.id)).where(
            Referral.referrer_id == user_id,
            Referral.status == "confirmed",
        )
    )
    confirmed_count = c_res.scalar() or 0

    p_res = await session.execute(
        select(func.count(Referral.id)).where(
            Referral.referrer_id == user_id,
            Referral.status == "pending",
        )
    )
    pending_count = p_res.scalar() or 0

    r_res = await session.execute(
        select(func.count(Referral.id)).where(
            Referral.referrer_id == user_id,
            Referral.status == "revoked",
        )
    )
    revoked_count = r_res.scalar() or 0

    # Coupons
    coupons_res = await session.execute(
        select(ReferralCoupon)
        .where(ReferralCoupon.user_id == user_id)
        .order_by(ReferralCoupon.milestone.asc())
    )
    all_coupons = coupons_res.scalars().all()

    # Milestone calculation: every 5 confirmed friends, skipping already-used milestones
    used_milestones = {cp.milestone for cp in all_coupons if cp.is_used}
    next_milestone = ((confirmed_count // 5) + 1) * 5
    while next_milestone in used_milestones:
        next_milestone += 5
    friends_needed_for_next = max(0, next_milestone - confirmed_count)

    available_coupons = []
    used_coupons = []

    for cp in all_coupons:
        # A coupon is active if not used AND user still has at least its milestone confirmed referrals
        is_currently_valid = (not cp.is_used) and (confirmed_count >= cp.milestone)
        cp_dict = {
            "id": cp.id,
            "code": cp.code,
            "discount_percent": cp.discount_percent,
            "milestone": cp.milestone,
            "is_used": cp.is_used,
            "is_valid": is_currently_valid,
            "used_at": cp.used_at.isoformat() if cp.used_at else None,
            "discount_amount": cp.discount_amount,
            "created_at": cp.created_at.isoformat() if cp.created_at else None,
        }
        if cp.is_used:
            used_coupons.append(cp_dict)
        else:
            available_coupons.append(cp_dict)

    # Recent invites
    inv_res = await session.execute(
        select(Referral)
        .where(Referral.referrer_id == user_id)
        .order_by(desc(Referral.created_at))
        .limit(10)
    )
    invites_records = inv_res.scalars().all()
    invites_out = []
    for inv in invites_records:
        u_res = await session.execute(select(User).where(User.telegram_id == inv.invitee_id))
        u = u_res.scalars().first()
        inv_name = u.name if u and u.name else f"ID: {inv.invitee_id}"
        invites_out.append({
            "invitee_id": inv.invitee_id,
            "name": inv_name,
            "status": inv.status,
            "was_member_before": inv.was_member_before,
            "created_at": inv.created_at.isoformat() if inv.created_at else None,
            "confirmed_at": inv.confirmed_at.isoformat() if inv.confirmed_at else None,
        })

    return {
        "user_id": user_id,
        "referral_link": ref_link,
        "confirmed_count": confirmed_count,
        "pending_count": pending_count,
        "revoked_count": revoked_count,
        "next_milestone": next_milestone,
        "friends_needed_for_next": friends_needed_for_next,
        "total_coupons_earned": len(all_coupons),
        "available_coupons": available_coupons,
        "used_coupons": used_coupons,
        "recent_invites": invites_out,
    }


async def validate_and_calculate_coupon_discount(
    session: AsyncSession,
    user_id: int,
    code: str,
    cart_items: List[Any],
    selected_product_id: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Validates a referral coupon and calculates 20% discount on 1 unit of chosen product.
    If no selected_product_id, selects highest unit price product in cart.
    Returns calculated discount amount and details.
    """
    clean_code = code.strip().upper()
    res = await session.execute(
        select(ReferralCoupon).where(ReferralCoupon.code == clean_code)
    )
    coupon = res.scalars().first()

    if not coupon:
        # Check standard PromoCode table as fallback
        pr_res = await session.execute(
            select(PromoCode).where(PromoCode.code == clean_code)
        )
        promo = pr_res.scalars().first()
        if not promo or not promo.is_active:
            return {"valid": False, "message": "Kupon topilmadi yoki faol emas ❌"}

        now = utcnow()
        if promo.valid_until and _ensure_utc(promo.valid_until) < now:
            return {"valid": False, "message": "Kupon muddati tugagan ❌"}

        if promo.max_uses and promo.used_count >= promo.max_uses:
            return {"valid": False, "message": "Kupondan foydalanish limiti tugagan ❌"}

        if not cart_items:
            return {"valid": False, "message": "Savat bo'sh 🛒"}

        def _extract_item_price_qty(it):
            if hasattr(it, "product_price") or hasattr(it, "price"):
                p = getattr(it, "product_price", getattr(it, "price", 0))
                q = getattr(it, "qty", 1)
            else:
                p = it.get("product_price", it.get("price", 0))
                q = it.get("qty", 1)
            return int(p or 0), int(q or 1)

        if promo.min_order_amount:
            cart_subtotal = sum(p * q for p, q in (_extract_item_price_qty(it) for it in cart_items))
            if cart_subtotal < promo.min_order_amount:
                min_fmt = f"{promo.min_order_amount:,}".replace(",", " ")
                return {
                    "valid": False,
                    "message": f"Ushbu promokod uchun minimal buyurtma summasi {min_fmt} so'm ❌",
                }

        target_item = None
        if selected_product_id:
            for it in cart_items:
                it_pid = getattr(it, "product_id", getattr(it, "id", None)) if hasattr(it, "product_id") else it.get("product_id", it.get("id"))
                if it_pid == selected_product_id:
                    target_item = it
                    break
            if not target_item:
                return {"valid": False, "message": "Tanlangan mahsulot savatda topilmadi ❌"}
        else:
            def get_item_price(it):
                if hasattr(it, "product_price"):
                    return it.product_price
                if hasattr(it, "price"):
                    return it.price
                return it.get("product_price", it.get("price", 0))

            target_item = max(cart_items, key=get_item_price)

        unit_price = getattr(target_item, "product_price", getattr(target_item, "price", 0)) if hasattr(target_item, "product_price") or hasattr(target_item, "price") else target_item.get("product_price", target_item.get("price", 0))
        title = getattr(target_item, "product_title", getattr(target_item, "title", "Mahsulot")) if hasattr(target_item, "product_title") or hasattr(target_item, "title") else target_item.get("product_title", target_item.get("title", "Mahsulot"))
        prod_id = getattr(target_item, "product_id", getattr(target_item, "id", None)) if hasattr(target_item, "product_id") else target_item.get("product_id", target_item.get("id"))

        if promo.discount_percent:
            discount_amount = int(unit_price * (promo.discount_percent / 100.0))
            pct_val = promo.discount_percent
        elif promo.discount_amount:
            discount_amount = min(int(unit_price), promo.discount_amount)
            pct_val = int((discount_amount / max(1, unit_price)) * 100)
        else:
            discount_amount = 0
            pct_val = 0

        formatted_discount = f"{discount_amount:,}".replace(",", " ") + " so'm"
        return {
            "valid": True,
            "coupon_id": promo.id,
            "code": promo.code,
            "discount_percent": pct_val,
            "milestone": None,
            "product_id": prod_id,
            "product_title": title,
            "unit_price": unit_price,
            "discount_amount": discount_amount,
            "formatted_discount_amount": formatted_discount,
            "message": f"'{title}' mahsulotiga chegirma (-{formatted_discount}) 🌸",
        }

    if coupon.user_id != user_id:
        return {"valid": False, "message": "Ushbu kupon sizning hisobingizga tegishli emas ❌"}

    if coupon.is_used:
        return {"valid": False, "message": "Bu kupon allaqachon ishlatilgan ❌"}

    # Verify that referrer currently has at least the required milestone confirmed referrals
    cnt_res = await session.execute(
        select(func.count(Referral.id)).where(
            Referral.referrer_id == user_id,
            Referral.status == "confirmed",
        )
    )
    confirmed_count = cnt_res.scalar() or 0
    if confirmed_count < coupon.milestone:
        return {
            "valid": False,
            "message": (
                f"Kupon faol emas: ushbu kupon uchun kamida {coupon.milestone} ta faol taklif qilingan "
                f"do'st bo'lishi kerak. Hozirda faol do'stlaringiz: {confirmed_count} ta 🌸"
            ),
        }

    if not cart_items:
        return {"valid": False, "message": "Savat bo'sh 🛒"}

    # Determine target product to discount
    target_item = None
    if selected_product_id:
        for it in cart_items:
            it_pid = getattr(it, "product_id", getattr(it, "id", None)) if hasattr(it, "product_id") else it.get("product_id", it.get("id"))
            if it_pid == selected_product_id:
                target_item = it
                break
        if not target_item:
            return {"valid": False, "message": "Tanlangan mahsulot savatda topilmadi ❌"}
    else:
        # Default to item with highest unit price to maximize benefit for customer
        def get_item_price(it):
            if hasattr(it, "product_price"):
                return it.product_price
            if hasattr(it, "price"):
                return it.price
            return it.get("product_price", it.get("price", 0))

        target_item = max(cart_items, key=get_item_price)

    unit_price = getattr(target_item, "product_price", getattr(target_item, "price", 0)) if hasattr(target_item, "product_price") or hasattr(target_item, "price") else target_item.get("product_price", target_item.get("price", 0))
    title = getattr(target_item, "product_title", getattr(target_item, "title", "Mahsulot")) if hasattr(target_item, "product_title") or hasattr(target_item, "title") else target_item.get("product_title", target_item.get("title", "Mahsulot"))
    prod_id = getattr(target_item, "product_id", getattr(target_item, "id", None)) if hasattr(target_item, "product_id") else target_item.get("product_id", target_item.get("id"))

    # Exactly 20% discount on 1 unit of product
    discount_amount = int(unit_price * 0.20)
    formatted_discount = f"{discount_amount:,}".replace(",", " ") + " so'm"

    return {
        "valid": True,
        "coupon_id": coupon.id,
        "code": coupon.code,
        "discount_percent": 20,
        "milestone": coupon.milestone,
        "product_id": prod_id,
        "product_title": title,
        "unit_price": unit_price,
        "discount_amount": discount_amount,
        "formatted_discount_amount": formatted_discount,
        "message": f"1 dona '{title}' mahsulotiga 20% chegirma (-{formatted_discount}) 🌸",
    }
