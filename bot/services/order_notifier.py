import logging
from typing import List, Dict, Any, Optional
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import select

from api.services.formatters import build_order_summary
from bot.loader import bot
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
        contact_username = contact_setting.value if contact_setting and contact_setting.value else "+998939029799"

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

        # 1. Send to all admins
        admin_markup = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="✅ Qabul qilindi", callback_data=f"order_accept_{order_id}"),
                    InlineKeyboardButton(text="❌ Bekor", callback_data=f"order_cancel_{order_id}"),
                ],
                [
                    InlineKeyboardButton(
                        text="👤 Mijoz profili",
                        url=f"https://t.me/{customer_username}" if customer_username else f"tg://user?id={user_id}"
                    )
                ]
            ]
        )

        for admin in admins:
            try:
                await bot.send_message(
                    chat_id=admin.telegram_id,
                    text=summaries["admin_text"],
                    reply_markup=admin_markup,
                )
            except Exception as e:
                logger.error(f"Failed to notify admin {admin.telegram_id} for order #{order_id}: {e}")

        # 2. Send to customer
        clean_contact = contact_username.replace("@", "")
        customer_markup = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=f"💌 @{clean_contact} ga yozish",
                        url=f"https://t.me/{clean_contact}"
                    )
                ]
            ]
        )

        try:
            await bot.send_message(
                chat_id=user_id,
                text=summaries["customer_text"],
                reply_markup=customer_markup,
            )
        except Exception as e:
            logger.error(f"Failed to send confirmation to customer {user_id} for order #{order_id}: {e}")


async def broadcast_live_order_proof(bot_instance: Any, order: Order) -> None:
    """
    Feature 18: Social Proof Order Broadcaster.
    Posts an anonymized receipt of the purchase to the designated channel or chat.
    Customer name is masked (e.g. M******a) and NO clickable profile link is included for 100% privacy!
    """
    if not bot_instance:
        return

    async with async_session_factory() as session:
        # Check target: live_orders_channel_id or channel_id
        res_t = await session.execute(select(Setting).where(Setting.key == "live_orders_channel_id"))
        row_t = res_t.scalars().first()
        target_chat = row_t.value if (row_t and row_t.value) else None

        if not target_chat:
            res_ch = await session.execute(select(Setting).where(Setting.key == "channel_id"))
            row_ch = res_ch.scalars().first()
            target_chat = row_ch.value if (row_ch and row_ch.value) else None

        if not target_chat:
            return

        from api.services.formatters import mask_customer_name, format_price

        masked_name = mask_customer_name(order.customer_name)
        item_titles = []
        for it in (order.items_snapshot or [])[:3]:
            title = it.get("title", "Kiyim")
            size = it.get("size")
            size_str = f" ({size})" if size else ""
            item_titles.append(f"• {title}{size_str}")

        items_text = "\n".join(item_titles) if item_titles else "• Go'zal kiyimlar"

        proof_text = (
            "🛍 <b>Yangi xarid rasmiylashtirildi!</b> ✨\n\n"
            f"👤 <b>Xaridor:</b> <code>{masked_name}</code> (shaxsiy profil yopiq 🔒)\n"
            f"📦 <b>Mahsulotlar:</b>\n{items_text}\n"
            f"💰 <b>Jami:</b> {format_price(order.total)}\n"
            "📍 <b>Yetkazish:</b> O'zbekiston bo'ylab 🚚\n"
            "✅ <b>Holati:</b> Qabul qilindi, Xitoydan yo'lga chiqmoqda ✨\n\n"
            "<i>Har bir mijozimizga ishonch uchun rahmat! 🌸</i>\n"
            "👉 @moonlight_chinese_bot"
        )

        try:
            target_id = int(target_chat) if (target_chat.startswith("-") or target_chat.isdigit()) else target_chat
            await bot_instance.send_message(
                chat_id=target_id,
                text=proof_text,
            )
        except Exception as e:
            logger.warning(f"Could not broadcast live order proof to {target_chat}: {e}")
