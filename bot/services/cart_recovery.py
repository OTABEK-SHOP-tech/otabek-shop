import asyncio
import logging
from datetime import datetime, timezone, timedelta
from html import escape
from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from sqlalchemy import select, and_

from api.config import settings
from bot.services.premium_emojis import upgrade_to_premium_emojis, strip_custom_emojis, make_premium_button
from db.models import User, CartItem, PromoCode
from db.session import async_session_factory

logger = logging.getLogger("moonlight_cart_recovery")


async def recover_abandoned_carts(bot_instance: Bot) -> int:
    """
    Scans for users with cart items older than 2 hours who haven't received
    a reminder in the last 24 hours, and sends a personalized cart reminder
    (advertising MOON10 only when that promo code is genuinely active in DB).
    """
    now = datetime.now(timezone.utc)
    two_hours_ago = now - timedelta(hours=2)
    one_day_ago = now - timedelta(hours=24)

    sent_count = 0
    blocked_any = False

    try:
        async with async_session_factory() as session:
            # Verify whether MOON10 promo code actually exists and is active before mentioning it
            promo_res = await session.execute(
                select(PromoCode).where(
                    PromoCode.code == "MOON10",
                    PromoCode.is_active == True,
                )
            )
            has_moon10 = promo_res.scalars().first() is not None

            # Find active, non-blocked users with cart items created before two_hours_ago
            stmt = (
                select(User)
                .join(CartItem, User.telegram_id == CartItem.user_id)
                .where(
                    and_(
                        CartItem.created_at <= two_hours_ago,
                        User.telegram_id.isnot(None),
                        User.blocked_bot == False,
                        (User.last_cart_reminder_sent.is_(None) | (User.last_cart_reminder_sent <= one_day_ago))
                    )
                )
                .distinct()
            )
            users_res = await session.execute(stmt)
            users = users_res.scalars().all()

            for user in users:
                # Fetch cart items for summary
                cart_stmt = select(CartItem).where(CartItem.user_id == user.telegram_id)
                c_res = await session.execute(cart_stmt)
                items = c_res.scalars().all()

                if not items:
                    continue

                display_name = user.name or "go'zal"
                if has_moon10:
                    raw_text = (
                        f"🌸 <b>Salom, {escape(display_name)}!</b> ✨\n\n"
                        f"Siz <b>Moonlight Chinese Shop</b> savatingizda ajoyib kiyimlarni unutib qoldirdingiz... 🛍️\n"
                        f"Tanlagan {len(items)} ta go'zal buyumingiz sizni kutmoqda!\n\n"
                        f"🎁 <i>Maxsus siz uchun 10% chegirma taqdim etamiz:</i>\n"
                        f"🏷 Promokod: <code>MOON10</code>\n\n"
                        f"Hoziroq savatingizga qaytib, buyurtmani 10% arzonroq rasmiylashtiring! 🌙"
                    )
                    webapp_url = f"{settings.WEBAPP_URL}?tab=bag&promo=MOON10"
                    btn_label = "Savatga qaytish (10% Chegirma)"
                else:
                    raw_text = (
                        f"🌸 <b>Salom, {escape(display_name)}!</b> ✨\n\n"
                        f"Siz <b>Moonlight Chinese Shop</b> savatingizda ajoyib buyumlarni qoldirib ketdingiz... 🛍️\n"
                        f"Tanlagan {len(items)} ta go'zal mahsulotingiz sizni kutmoqda!\n\n"
                        f"Hoziroq savatingizga qaytib, buyurtmani qulay narxda rasmiylashtiring! 🌙"
                    )
                    webapp_url = f"{settings.WEBAPP_URL}?tab=bag"
                    btn_label = "Savatga qaytish 🛍️"

                reminder_text = upgrade_to_premium_emojis(raw_text)
                keyboard = InlineKeyboardMarkup(
                    inline_keyboard=[
                        [
                            make_premium_button(
                                text=btn_label,
                                web_app=WebAppInfo(url=webapp_url)
                            )
                        ]
                    ]
                )
                plain_keyboard = InlineKeyboardMarkup(
                    inline_keyboard=[
                        [
                            InlineKeyboardButton(
                                text=btn_label,
                                web_app=WebAppInfo(url=webapp_url)
                            )
                        ]
                    ]
                )

                try:
                    try:
                        await bot_instance.send_message(
                            chat_id=user.telegram_id,
                            text=reminder_text,
                            parse_mode="HTML",
                            reply_markup=keyboard
                        )
                    except TelegramForbiddenError:
                        raise
                    except Exception:
                        await bot_instance.send_message(
                            chat_id=user.telegram_id,
                            text=strip_custom_emojis(raw_text),
                            parse_mode="HTML",
                            reply_markup=plain_keyboard
                        )
                    user.last_cart_reminder_sent = now
                    sent_count += 1
                    logger.info("Sent abandoned cart recovery reminder to user %s", user.telegram_id)
                except TelegramForbiddenError:
                    user.blocked_bot = True
                    blocked_any = True
                    logger.info("User %s blocked the bot; marked blocked_bot=True", user.telegram_id)
                except Exception as send_err:
                    logger.warning("Could not send cart recovery to user %s: %s", user.telegram_id, send_err)

            if sent_count > 0 or blocked_any:
                await session.commit()

    except Exception as e:
        logger.error("Error in recover_abandoned_carts: %s", e)

    return sent_count


async def run_cart_recovery_scheduler(bot_instance: Bot, interval_seconds: int = 1800):
    """Periodic worker running cart recovery check every interval_seconds (default 30 min)."""
    logger.info("Starting Moonlight abandoned cart recovery worker...")
    while True:
        try:
            await recover_abandoned_carts(bot_instance)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error("Unhandled error in cart recovery worker: %s", e)

        try:
            await asyncio.sleep(interval_seconds)
        except asyncio.CancelledError:
            break
