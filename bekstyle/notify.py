"""Telegram side effects: channel posts, order alerts, status messages, broadcast."""

import asyncio
import logging

from aiogram import Bot
from aiogram.exceptions import (
    TelegramAPIError,
    TelegramBadRequest,
    TelegramForbiddenError,
    TelegramRetryAfter,
)
from aiogram.types import FSInputFile, InlineKeyboardMarkup, InputMediaPhoto, Message
from sqlalchemy import select, update

from bekstyle import texts as t
from bekstyle.db import Admin, Order, Product, User, async_session, get_setting
from bekstyle.keyboards import Button, order_admin_kb
from bekstyle.visuals import BANNER

logger = logging.getLogger(__name__)

BROADCAST_DELAY_S = 0.05  # ~20 msg/s, under Telegram's 30/s bot limit
_file_id_cache: dict[str, str] = {}

PhotoInput = str | FSInputFile


def banner_photo() -> PhotoInput:
    return _file_id_cache.get("banner") or FSInputFile(BANNER)


def remember_banner(photo: PhotoInput, sent: Message) -> None:
    """After the first upload of the banner file, reuse Telegram's file_id instead of re-uploading."""
    if isinstance(photo, FSInputFile) and sent.photo:
        _file_id_cache["banner"] = sent.photo[-1].file_id


def first_photo(product: Product) -> PhotoInput:
    return product.photos[0] if product.photos else banner_photo()


async def safe_edit_text(message: Message, text: str, markup: InlineKeyboardMarkup | None = None) -> None:
    try:
        await message.edit_text(text, reply_markup=markup)
    except TelegramBadRequest as exc:
        if "message is not modified" not in str(exc):
            raise


async def send_album(bot: Bot, chat_id: int | str, photos: list[str], caption: str | None = None) -> list[Message]:
    sent: list[Message] = []
    for start in range(0, len(photos), 10):
        chunk = photos[start : start + 10]
        media = [
            InputMediaPhoto(media=p, caption=caption if start == 0 and i == 0 else None) for i, p in enumerate(chunk)
        ]
        sent += await bot.send_media_group(chat_id=chat_id, media=media)
    return sent


async def post_product_to_channel(bot: Bot, product: Product) -> tuple[bool, str]:
    async with async_session() as session:
        channel_id = await get_setting(session, "channel_id")
        delivery = await get_setting(session, "delivery_text")
    if not channel_id:
        return False, "Kanal ulanmagan: ⚙️ Sozlamalar → 🔗 Kanalni ulash."
    caption = t.channel_caption(
        product.title,
        product.price,
        product.category.name,
        product.colors,
        product.sizes,
        product.description,
        delivery,
    )
    me = await bot.get_me()
    order_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                Button(
                    text="🛒 Buyurtma berish",
                    url=f"https://t.me/{me.username}?start=p_{product.id}",
                )
            ]
        ]
    )
    try:
        if len(product.photos) > 1:
            sent = await send_album(bot, channel_id, product.photos, caption)
            await bot.send_message(
                channel_id,
                f"👆 <b>{t.BRAND}</b> · buyurtma uchun:",
                reply_markup=order_kb,
            )
            message_id = sent[0].message_id
        else:
            msg = await bot.send_photo(channel_id, first_photo(product), caption=caption, reply_markup=order_kb)
            message_id = msg.message_id
    except TelegramAPIError as exc:  # any Telegram error is reported back to the admin as text
        logger.warning("Channel post for product %s failed: %s", product.id, exc)
        return False, f"Telegram xatosi: {exc}"
    async with async_session() as session:
        await session.execute(update(Product).where(Product.id == product.id).values(channel_message_id=message_id))
        await session.commit()
    return True, "Kanalga joylandi ✅"


def order_admin_view(order: Order) -> tuple[str, InlineKeyboardMarkup]:
    customer = t.customer_block(
        order.user_id,
        order.customer_name,
        order.customer_username,
        order.phone,
        order.address,
    )
    text = t.order_text(order.id, order.status, order.items, order.total, order.created_at, customer)
    return text, order_admin_kb(order.id, order.status, order.customer_username)


async def notify_admins_new_order(bot: Bot, order: Order) -> None:
    async with async_session() as session:
        admin_ids = list((await session.scalars(select(Admin.telegram_id))).all())
    text, markup = order_admin_view(order)
    for admin_id in admin_ids:
        try:
            await bot.send_message(admin_id, "🔔 <b>Yangi buyurtma!</b>\n\n" + text, reply_markup=markup)
        except TelegramAPIError as exc:  # one unreachable admin must not block the others
            logger.warning("Order #%s alert to admin %s failed: %s", order.id, admin_id, exc)


async def notify_customer_status(bot: Bot, order: Order) -> None:
    async with async_session() as session:
        delivery = await get_setting(session, "delivery_text")
        contact = await get_setting(session, "contact_username")
    try:
        await bot.send_message(order.user_id, t.status_message(order.id, order.status, delivery, contact))
    except TelegramAPIError as exc:  # customer may have blocked the bot; the status change itself is saved
        logger.warning("Status message for order #%s failed: %s", order.id, exc)


async def _copy_with_retry(bot: Bot, user_id: int, from_chat_id: int, message_id: int) -> None:
    try:
        await bot.copy_message(user_id, from_chat_id, message_id)
    except TelegramRetryAfter as exc:
        await asyncio.sleep(exc.retry_after + 0.5)
        await bot.copy_message(user_id, from_chat_id, message_id)


async def run_broadcast(bot: Bot, from_chat_id: int, message_id: int, admin_id: int) -> None:
    async with async_session() as session:
        user_ids = list((await session.scalars(select(User.telegram_id).where(User.blocked_bot.is_(False)))).all())
    sent, failed = 0, 0
    blocked: list[int] = []
    for user_id in user_ids:
        try:
            await _copy_with_retry(bot, user_id, from_chat_id, message_id)
            sent += 1
        except TelegramForbiddenError:
            blocked.append(user_id)
        except TelegramAPIError as exc:  # keep going; the summary reports the failures
            logger.warning("Broadcast to %s failed: %s", user_id, exc)
            failed += 1
        await asyncio.sleep(BROADCAST_DELAY_S)
    if blocked:
        async with async_session() as session:
            await session.execute(update(User).where(User.telegram_id.in_(blocked)).values(blocked_bot=True))
            await session.commit()
    await bot.send_message(
        admin_id,
        f"📣 <b>Xabar tarqatildi</b>\n\n👥 Jami: {len(user_ids)}\n✅ Yetdi: {sent}\n🚫 Bloklagan: {len(blocked)}\n⚠️ Xato: {failed}",
    )
