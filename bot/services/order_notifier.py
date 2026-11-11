import logging
from typing import List, Dict, Any, Optional
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import select

from api.services.formatters import build_order_summary, format_price
from bot.loader import bot
from bot.services.premium_emojis import (
    upgrade_to_premium_emojis,
    make_premium_button,
    PREMIUM_BTN_BAG_ID,
    PREMIUM_BTN_STAR_ID,
)
from db.models import Admin, Setting, User, Order
from db.session import async_session_factory
from html import escape

logger = logging.getLogger(__name__)


async def send_payment_instructions(
    order_id: int,
    user_id: int,
    customer_name: str,
    customer_username: Optional[str] = None,
    items: Optional[List[Dict[str, Any]]] = None,
    total: int = 0,
    estimated_cargo: int = 0,
) -> None:
    """
    Sends payment instructions to the customer immediately after order creation.
    CRITICAL: Does NOT notify admins. Admins are only notified after receipt upload.
    """
    if not bot:
        logger.info(f"Bot not active, skipped payment instructions for order #{order_id}")
        return

    async with async_session_factory() as session:
        # Get contact username
        res_contact = await session.execute(select(Setting).where(Setting.key == "contact_username"))
        contact_setting = res_contact.scalars().first()
        contact_username = contact_setting.value if contact_setting and contact_setting.value else "MOONLIGHT_ADMINNN"
        clean_contact = contact_username.replace("@", "")

        # Get payment card details
        res_card = await session.execute(select(Setting).where(Setting.key == "payment_card"))
        card_setting = res_card.scalars().first()
        payment_card_text = card_setting.value if card_setting and card_setting.value else "9860 0301 0204 8413 (Gulmira M.)"

    cargo_text = f"📦 <b>Taxminiy kargo:</b> {format_price(estimated_cargo)}\n" if estimated_cargo > 0 else ""

    items_block = ""
    if items:
        item_lines = []
        for idx, item in enumerate(items[:5], 1):
            t = item.get("title", "Mahsulot")
            q = item.get("qty", 1)
            p = item.get("price", 0)
            item_lines.append(f"  {idx}. {escape(str(t))} — {q} x {format_price(p)}")
        if len(items) > 5:
            item_lines.append(f"  ... va yana {len(items) - 5} ta mahsulot")
        items_block = f"📋 <b>Tanlangan mahsulotlar:</b>\n" + "\n".join(item_lines) + "\n\n"

    payment_msg = (
        f"🌸 <b>Rahmat, {escape(customer_name or 'Mijoz')}!</b> 💗\n\n"
        f"Buyurtmangiz <b>#{order_id}</b> rasmiylashtirildi.\n\n"
        f"{items_block}"
        f"💰 <b>To'lov summasi:</b> <b>{format_price(total)}</b>\n"
        f"{cargo_text}"
        f"💳 <b>To'lov uchun karta (rekvizitlar):</b>\n"
        f"<code>{escape(payment_card_text)}</code>\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"📸 <b>Iltimos, to'lov chekini (skrinshot yoki rasm shaklida) ushbu botga yuboring! "
        f"Chekni yubormaguningizcha buyurtmangiz adminlarga yuborilmaydi.</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"<i>To'lov amalga oshirilgach, chek rasmini to'g'ridan-to'g'ri ushbu chatga yuboring</i> 💌"
    )

    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="💌 Moonlight Shop Adminga bog'lanish",
                    url=f"https://t.me/{clean_contact}",
                    icon_custom_emoji_id=PREMIUM_BTN_STAR_ID,
                    style="primary",
                )
            ]
        ]
    )
    fallback_markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="💌 Moonlight Shop Adminga bog'lanish",
                    url=f"https://t.me/{clean_contact}",
                )
            ]
        ]
    )

    try:
        try:
            await bot.send_message(
                chat_id=user_id,
                text=upgrade_to_premium_emojis(payment_msg),
                reply_markup=markup,
                parse_mode="HTML",
            )
        except Exception:
            await bot.send_message(
                chat_id=user_id,
                text=payment_msg,
                reply_markup=fallback_markup,
                parse_mode="HTML",
            )
        logger.info(f"Sent payment instructions for order #{order_id} to user {user_id}")
    except Exception as e:
        logger.error(f"Failed to send payment instructions to user {user_id} for order #{order_id}: {e}")


async def notify_new_order(
    order_id: int,
    user_id: int,
    customer_name: str,
    customer_username: Optional[str] = None,
    items: Optional[List[Dict[str, Any]]] = None,
    total: int = 0,
    estimated_cargo: int = 0,
) -> None:
    """
    Backwards-compatible wrapper: sends payment instructions to customer.
    Does NOT notify admins until payment receipt is submitted.
    """
    await send_payment_instructions(
        order_id=order_id,
        user_id=user_id,
        customer_name=customer_name,
        customer_username=customer_username,
        items=items or [],
        total=total,
        estimated_cargo=estimated_cargo,
    )


async def notify_admins_new_receipt(order_id: int) -> None:
    """
    Sends the uploaded check photo to all admins with detailed caption
    and action buttons: Accept, Cancel, Customer Profile.
    """
    if not bot:
        logger.info(f"Bot not active, skipped admin receipt notification for order #{order_id}")
        return

    async with async_session_factory() as session:
        res = await session.execute(select(Order).where(Order.id == order_id))
        order = res.scalars().first()
        if not order:
            logger.error(f"Order #{order_id} not found for receipt notification")
            return

        res_admins = await session.execute(select(Admin))
        db_admins = res_admins.scalars().all()
        admin_ids = {a.telegram_id for a in db_admins}
        # Permanent store admins
        admin_ids.add(8643984824)  # Otabek
        admin_ids.add(8413799379)  # Gulmira opa

        username_display = f"@{order.customer_username}" if order.customer_username else "username yo'q"
        safe_customer_name = order.customer_name or "Mijoz"
        user_link = f"<a href='tg://user?id={order.user_id}'>{escape(safe_customer_name)}</a>"

        item_lines = []
        for idx, it in enumerate((order.items_snapshot or [])[:5], 1):
            title = it.get("title", "Mahsulot")
            qty = it.get("qty", 1)
            price = it.get("price", 0)
            item_lines.append(f"  {idx}. {escape(str(title))} ({qty}x{format_price(price)})")
        if len(order.items_snapshot or []) > 5:
            item_lines.append(f"  ... va yana {len(order.items_snapshot) - 5} ta mahsulot")
        items_block = "\n".join(item_lines) if item_lines else "  1 ta mahsulot"

        cargo_line = f"\n📦 <b>Kargo:</b> ~{format_price(order.estimated_cargo)}" if order.estimated_cargo > 0 else ""
        cashback_line = f"\n🪙 <b>Keshbek ishlatildi:</b> -{format_price(order.cashback_used)}" if order.cashback_used > 0 else ""

        caption = (
            f"🛍️ <b>Yangi to'lov cheki keldi! Buyurtma #{order.id}</b> 🌸\n\n"
            f"👤 <b>Mijoz:</b> {user_link} ({username_display})\n"
            f"🆔 <b>Telegram ID:</b> <code>{order.user_id}</code>\n\n"
            f"📋 <b>Mahsulotlar:</b>\n{items_block}\n\n"
            f"💰 <b>To'lov summasi:</b> <b>{format_price(order.total)}</b>"
            f"{cargo_line}"
            f"{cashback_line}\n\n"
            f"👇 <b>Chekni tekshirib, quyidagi tugmalar orqali qabul qiling yoki rad eting:</b>"
        )
        caption = upgrade_to_premium_emojis(caption)
        if len(caption) > 1020:
            caption = caption[:1015] + "..."

        customer_profile_url = (
            f"https://t.me/{order.customer_username}"
            if order.customer_username
            else f"tg://user?id={order.user_id}"
        )

        admin_markup = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="✅ Qabul qilish (Tasdiqlash)",
                        callback_data=f"order_accept_{order.id}",
                        style="success",
                    ),
                    InlineKeyboardButton(
                        text="❌ Rad etish (Bekor)",
                        callback_data=f"order_cancel_{order.id}",
                        style="danger",
                    ),
                ],
                [
                    InlineKeyboardButton(
                        text="👤 Mijoz profili",
                        url=customer_profile_url,
                        style="primary",
                    )
                ]
            ]
        )
        admin_fallback_markup = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="✅ Qabul qilish (Tasdiqlash)",
                        callback_data=f"order_accept_{order.id}",
                    ),
                    InlineKeyboardButton(
                        text="❌ Rad etish (Bekor)",
                        callback_data=f"order_cancel_{order.id}",
                    ),
                ],
                [
                    InlineKeyboardButton(
                        text="👤 Mijoz profili",
                        url=customer_profile_url,
                    )
                ]
            ]
        )

        for aid in admin_ids:
            try:
                if order.receipt_photo_id:
                    try:
                        await bot.send_photo(
                            chat_id=aid,
                            photo=order.receipt_photo_id,
                            caption=caption,
                            reply_markup=admin_markup,
                            parse_mode="HTML",
                        )
                    except Exception as photo_err:
                        logger.warning(f"send_photo failed for admin {aid} ({photo_err}), attempting send_document...")
                        try:
                            await bot.send_document(
                                chat_id=aid,
                                document=order.receipt_photo_id,
                                caption=caption,
                                reply_markup=admin_markup,
                                parse_mode="HTML",
                            )
                        except Exception as doc_err:
                            logger.warning(f"send_document failed for admin {aid} ({doc_err}), falling back to text message...")
                            await bot.send_message(
                                chat_id=aid,
                                text=caption,
                                reply_markup=admin_fallback_markup,
                                parse_mode="HTML",
                            )
                else:
                    try:
                        await bot.send_message(
                            chat_id=aid,
                            text=caption,
                            reply_markup=admin_markup,
                            parse_mode="HTML",
                        )
                    except Exception:
                        await bot.send_message(
                            chat_id=aid,
                            text=caption,
                            reply_markup=admin_fallback_markup,
                            parse_mode="HTML",
                        )
                logger.info(f"Notified admin {aid} of receipt for order #{order.id}")
            except Exception as e:
                logger.error(f"Failed to send receipt notification to admin {aid} for order #{order_id}: {e}")


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

    masked_name = mask_customer_name(order.customer_name or "Mijoz")
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
        item_lines.append(f"{TG_PRODUCT} <b>Mahsulot:</b> {escape(str(title))}{size_str}{color_str}")

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
        + f"{TG_TIME} <b>Vaqt:</b> {time_str} (Toshkent)\n\n"
        + f"Savollar yoki buyurtma berish uchun Moonlight Shop adminiga bog'laning 💌</blockquote>"
    )

    contact_username = "MOONLIGHT_ADMINNN"
    try:
        async with async_session_factory() as session:
            c_row = (await session.execute(select(Setting).where(Setting.key == "contact_username"))).scalars().first()
            if c_row and c_row.value:
                contact_username = c_row.value.lstrip("@")
    except Exception:
        pass
    clean_contact = contact_username.replace("@", "")

    # Premium Buttons with animated custom emojis & styles
    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="💌 Moonlight Shop Adminga bog'lanish",
                    url=f"https://t.me/{clean_contact}",
                    icon_custom_emoji_id=PREMIUM_BTN_STAR_ID,
                    style="primary",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🛍️ Moonlight Do'koniga kirish",
                    url="https://t.me/moonlight_chinese_bot",
                    icon_custom_emoji_id=PREMIUM_BTN_BAG_ID,
                    style="primary",
                )
            ]
        ]
    )
    fallback_markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💌 Moonlight Shop Adminga bog'lanish", url=f"https://t.me/{clean_contact}")],
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
