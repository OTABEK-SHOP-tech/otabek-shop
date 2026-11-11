import logging
from typing import List, Dict, Any, Optional
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import select

from api.services.formatters import build_order_summary
from bot.loader import bot
from bot.services.premium_emojis import (
    upgrade_to_premium_emojis,
    make_premium_button,
    PREMIUM_BTN_BAG_ID,
    PREMIUM_BTN_STAR_ID,
)
from db.models import Admin, Setting, User, Order
from db.session import async_session_factory

logger = logging.getLogger(__name__)


async def notify_new_order(
    order_id: int,
    user_id: int,
    customer_name: str,
    customer_username: Optional[str],
    items: List[Dict[str, Any]],
    total: int,
    estimated_cargo: int = 0,
) -> None:
    if not bot:
        logger.info(f"Bot not active, skipped Telegram notification for order #{order_id}")
        return

    async with async_session_factory() as session:
        # Get contact username
        res_contact = await session.execute(select(Setting).where(Setting.key == "contact_username"))
        contact_setting = res_contact.scalars().first()
        contact_username = contact_setting.value if contact_setting and contact_setting.value else "MOONLIGHT_ADMINNN"

        # Get all admins
        res_admins = await session.execute(select(Admin))
        admins = res_admins.scalars().all()

        summaries = build_order_summary(
            order_id=order_id,
            user_id=user_id,
            customer_name=customer_name,
            customer_username=customer_username,
            items=items,
            total=total,
            estimated_cargo=estimated_cargo,
            contact_username=contact_username,
        )

        # 1. Send to all admins with styled buttons
        admin_markup = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="✅ Qabul qilindi",
                        callback_data=f"order_accept_{order_id}",
                        style="success",
                    ),
                    InlineKeyboardButton(
                        text="❌ Bekor",
                        callback_data=f"order_cancel_{order_id}",
                        style="danger",
                    ),
                ],
                [
                    InlineKeyboardButton(
                        text="👤 Mijoz profili",
                        url=f"https://t.me/{customer_username}" if customer_username else f"tg://user?id={user_id}",
                        style="primary",
                    )
                ]
            ]
        )

        admin_text = upgrade_to_premium_emojis(summaries["admin_text"])
        for admin in admins:
            try:
                await bot.send_message(
                    chat_id=admin.telegram_id,
                    text=admin_text,
                    reply_markup=admin_markup,
                    parse_mode="HTML",
                )
            except Exception as e:
                logger.error(f"Failed to notify admin {admin.telegram_id} for order #{order_id}: {e}")

        # 2. Send to customer with premium styling
        clean_contact = contact_username.replace("@", "")
        customer_markup = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    make_premium_button(
                        text=f"@{clean_contact} ga yozish",
                        url=f"https://t.me/{clean_contact}",
                        icon_id=PREMIUM_BTN_BAG_ID,
                        style="primary",
                    )
                ]
            ]
        )

        customer_text = upgrade_to_premium_emojis(summaries["customer_text"])
        try:
            await bot.send_message(
                chat_id=user_id,
                text=customer_text,
                reply_markup=customer_markup,
                parse_mode="HTML",
            )
        except Exception as e:
            logger.error(f"Failed to send confirmation to customer {user_id} for order #{order_id}: {e}")

        # 3. Broadcast to Live Orders Social Proof Group (@moonlight_shop_otzv)
        try:
            res_order = await session.execute(select(Order).where(Order.id == order_id))
            db_order = res_order.scalars().first()
            if db_order:
                await broadcast_live_order_proof(bot, db_order)
        except Exception as proof_err:
            logger.warning(f"Could not broadcast proof for order #{order_id}: {proof_err}")


DEFAULT_PROOF_CHAT = -1004297799216  # @moonlight_shop_otzv ("Moonlight shop otziv")

# Premium Animated Custom Emojis (Bot API 7.0+ <tg-emoji emoji-id="...">)
# Unlocked via bot owner's Telegram Premium subscription
TG_MOON = '<tg-emoji emoji-id="5429099589997184246">🌙</tg-emoji>'
TG_PARTY = '<tg-emoji emoji-id="5436040291507247633">🎉</tg-emoji>'
TG_PIN = '<tg-emoji emoji-id="5429270061544130296">📍</tg-emoji>'
TG_USER = '<tg-emoji emoji-id="5373012449597335010">👤</tg-emoji>'
TG_PRODUCT = '<tg-emoji emoji-id="5429587463922272406">👛</tg-emoji>'
TG_STAR = '<tg-emoji emoji-id="5429351167706547656">🌟</tg-emoji>'
TG_MONEY = '<tg-emoji emoji-id="5375296873982604963">💰</tg-emoji>'
TG_CARGO = '<tg-emoji emoji-id="5429388216094444138">🎁</tg-emoji>'
TG_TIME = '<tg-emoji emoji-id="5431807687136395567">⏰</tg-emoji>'
TG_SAKURA = '<tg-emoji emoji-id="5465119341815027379">🌸</tg-emoji>'


async def broadcast_live_order_proof(bot_instance: Any, order: Order, target_chat_override: Optional[Any] = None) -> None:
    """
    Feature 18: Social Proof Order Broadcaster.
    Posts an aesthetic receipt of the purchase formatted like Telegram blockquote (like second pic).
    Customer name and ID are masked (e.g. O****k, ID: 8643***824) and NO clickable profile link is included for 100% privacy!
    Uses Telegram Premium animated custom emojis (<tg-emoji>) for boutique elegance.
    """
    if not bot_instance:
        return

    target_chat = target_chat_override
    if not target_chat:
        try:
            async with async_session_factory() as session:
                res_t = await session.execute(select(Setting).where(Setting.key == "live_orders_channel_id"))
                row_t = res_t.scalars().first()
                if row_t and row_t.value:
                    target_chat = row_t.value
        except Exception:
            pass

    if not target_chat:
        target_chat = DEFAULT_PROOF_CHAT

    from api.services.formatters import mask_customer_name, mask_user_id, format_price
    from datetime import datetime, timezone, timedelta
    from html import escape

    tashkent_now = datetime.now(timezone(timedelta(hours=5)))
    time_str = tashkent_now.strftime("%d-%b-%Y %H:%M")

    masked_name = mask_customer_name(order.customer_name)
    masked_id = mask_user_id(order.user_id)

    item_lines = []
    total_qty = 0
    for it in (order.items_snapshot or [])[:4]:
        title = it.get("title") or it.get("product_title", "Kiyim")
        qty = it.get("qty", 1)
        total_qty += qty
        size = it.get("size")
        size_str = f" ({size})" if size else ""
        color = it.get("color")
        color_str = f" [{color}]" if color else ""
        item_lines.append(f"{TG_PRODUCT} <b>Mahsulot:</b> {escape(title)}{size_str}{color_str}")

    if not item_lines:
        item_lines = [f"{TG_PRODUCT} <b>Mahsulot:</b> Go'zal libos"]
        total_qty = 1
    elif len(order.items_snapshot or []) > 4:
        item_lines.append(f"• va yana {len(order.items_snapshot) - 4} ta buyum...")

    products_block = "\n".join(item_lines)

    proof_text = (
        f"{TG_MOON} <b>Moonlight Alerts</b>\n\n"
        f"<blockquote>{TG_PARTY} <b>Yangi Xarid! / New Purchase!</b>\n\n"
        f"{TG_PIN} <b>ID:</b> <code>{masked_id}</code>\n"
        f"{TG_USER} <b>Xaridor:</b> <code>{masked_name}</code>\n"
        f"{products_block}\n"
        f"{TG_STAR} <b>Miqdor:</b> {total_qty} dona\n"
        f"{TG_MONEY} <b>Summa:</b> {format_price(order.total)}\n"
        + (f"{TG_CARGO} <b>Kargo:</b> ~{format_price(order.estimated_cargo)}\n" if order.estimated_cargo else "")
        + f"{TG_TIME} <b>Vaqt:</b> {time_str} (Toshkent)</blockquote>"
    )

    # Premium Button with animated custom emoji & style
    btn_kwargs = {
        "text": "Moonlight Do'koniga kirish",
        "url": "https://t.me/moonlight_chinese_bot",
        "icon_custom_emoji_id": "5373052667671093676",
        "style": "primary",
    }
    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(**btn_kwargs)]
        ]
    )
    fallback_markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🛍️ Moonlight Do'koniga kirish", url="https://t.me/moonlight_chinese_bot")]
        ]
    )

    try:
        target_id = int(target_chat) if (str(target_chat).startswith("-") or str(target_chat).isdigit()) else target_chat
        try:
            await bot_instance.send_message(
                chat_id=target_id,
                text=proof_text,
                parse_mode="HTML",
                reply_markup=markup,
            )
        except Exception as html_err:
            logger.warning(f"Custom emoji proof failed ({html_err}), falling back to plain emojis...")
            import re
            fallback_text = re.sub(r'<tg-emoji emoji-id="[^"]*">([^<]+)</tg-emoji>', r'\1', proof_text)
            await bot_instance.send_message(
                chat_id=target_id,
                text=fallback_text,
                parse_mode="HTML",
                reply_markup=fallback_markup,
            )
        logger.info(f"Broadcasted live order proof for order #{order.id} to {target_chat}")
    except Exception as e:
        logger.warning(f"Could not broadcast live order proof to {target_chat}: {e}")
