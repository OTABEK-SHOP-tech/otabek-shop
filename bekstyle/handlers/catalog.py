"""Customer catalog: categories, swipeable product cards, colour/size picker, add to cart."""

from dataclasses import dataclass

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InputMediaPhoto, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bekstyle import texts as t
from bekstyle.db import Product, async_session, get_setting
from bekstyle.handlers import cb_int, cb_message
from bekstyle.keyboards import card_kb, categories_kb, picker_kb
from bekstyle.notify import (
    PhotoInput,
    first_photo,
    remember_banner,
    safe_edit_text,
    send_album,
)
from bekstyle.services import (
    add_to_cart,
    cart_count,
    catalog_product_ids,
    categories_with_counts,
)

router = Router(name="catalog")


@dataclass(frozen=True)
class Card:
    photo: PhotoInput
    caption: str
    markup: InlineKeyboardMarkup


async def build_card(
    session: AsyncSession,
    user_id: int,
    cid: int,
    idx: int = 0,
    product_id: int | None = None,
) -> Card | None:
    """Card at position idx of list cid (0 = new arrivals), or for product_id within that list."""
    ids = await catalog_product_ids(session, cid)
    if product_id is not None:
        position, total = (ids.index(product_id), len(ids)) if product_id in ids else (0, 1)
    elif ids:
        position, total = idx % len(ids), len(ids)
        product_id = ids[position]
    else:
        return None
    product = await session.get(Product, product_id)
    if product is None:
        return None
    delivery = await get_setting(session, "delivery_text")
    caption = t.product_caption(
        product.title,
        product.price,
        product.colors,
        product.sizes,
        product.description,
        delivery,
        product.in_stock,
    )
    markup = card_kb(
        product.id,
        cid,
        position,
        total,
        product.in_stock,
        len(product.photos),
        await cart_count(session, user_id),
    )
    return Card(first_photo(product), caption, markup)


async def send_card(message: Message, card: Card) -> None:
    sent = await message.answer_photo(card.photo, caption=card.caption, reply_markup=card.markup)
    remember_banner(card.photo, sent)


async def send_product(message: Message, user_id: int, product_id: int) -> bool:
    """Deep link from a channel post (/start p_<id>)."""
    async with async_session() as session:
        product = await session.get(Product, product_id)
        card = await build_card(session, user_id, product.category_id, product_id=product_id) if product else None
    if card is None:
        return False
    await send_card(message, card)
    return True


async def _show_categories(message: Message, edit: bool) -> None:
    async with async_session() as session:
        rows = await categories_with_counts(session, in_stock_only=True)
    items = [(cat.id, f"{cat.emoji} {cat.name}", count) for cat, count in rows if count]
    if not items:
        text, markup = (
            f"🖤 <b>{t.BRAND}</b>\n\nKatalog tez orada to'ladi — yangi drop'lar yo'lda 🔥",
            None,
        )
    else:
        text, markup = "🛍 <b>Katalog</b>\nBo'limni tanlang 👇", categories_kb(items)
    if edit:
        await safe_edit_text(message, text, markup)
    else:
        await message.answer(text, reply_markup=markup)


@router.message(F.text == t.BTN_CATALOG)
async def on_catalog(message: Message) -> None:
    await _show_categories(message, edit=False)


@router.callback_query(F.data == "cats")
async def on_categories(callback: CallbackQuery) -> None:
    msg = cb_message(callback)
    if msg:
        await _show_categories(msg, edit=bool(msg.text))
    await callback.answer()


@router.message(F.text == t.BTN_NEW)
async def on_new_arrivals(message: Message) -> None:
    if message.from_user is None:
        return
    async with async_session() as session:
        card = await build_card(session, message.from_user.id, cid=0)
    if card is None:
        await message.answer("🔥 Yangi drop'lar tez orada. Kanalni kuzatib boring!")
        return
    await send_card(message, card)


async def _edit_card(msg: Message, card: Card) -> None:
    try:
        await msg.edit_media(
            InputMediaPhoto(media=card.photo, caption=card.caption),
            reply_markup=card.markup,
        )
    except TelegramBadRequest as exc:
        if "message is not modified" not in str(exc):
            raise


@router.callback_query(F.data.startswith("cat:"))
async def on_card_nav(callback: CallbackQuery) -> None:
    async with async_session() as session:
        card = await build_card(session, callback.from_user.id, cb_int(callback, 1), cb_int(callback, 2))
    msg = cb_message(callback)
    if card is None:
        await callback.answer("Bu bo'limda hozircha mahsulot yo'q", show_alert=True)
        return
    if msg and msg.photo:
        await _edit_card(msg, card)
    elif msg:
        await send_card(msg, card)
    await callback.answer()


@router.callback_query(F.data.startswith("ph:"))
async def on_all_photos(callback: CallbackQuery, bot: Bot) -> None:
    async with async_session() as session:
        product = await session.get(Product, cb_int(callback, 1))
    msg = cb_message(callback)
    if not product or not product.photos or not msg:
        await callback.answer("Rasmlar topilmadi", show_alert=True)
        return
    await callback.answer()
    await send_album(bot, msg.chat.id, product.photos)


def _pick(options: list[str], raw: str) -> tuple[bool, str | None]:
    if not options:
        return True, None
    if raw.isdecimal() and int(raw) < len(options):
        return True, options[int(raw)]
    return False, None


@router.callback_query(F.data.startswith("b:"))
async def on_buy(callback: CallbackQuery) -> None:
    """b:<pid>:<cid>:<colour idx|x>:<size idx|x> — asks colour, then size, then adds to cart."""
    _, pid_raw, cid_raw, ci, si = (callback.data or "").split(":")
    pid, cid, user_id = int(pid_raw), int(cid_raw), callback.from_user.id
    msg = cb_message(callback)
    async with async_session() as session:
        product = await session.get(Product, pid)
        if product is None or not product.in_stock:
            await callback.answer("⚪️ Bu model hozircha tugagan", show_alert=True)
            return
        back = f"bk:{pid}:{cid}"
        if product.colors and ci == "x":
            if msg:
                await msg.edit_reply_markup(
                    reply_markup=picker_kb(product.colors, lambda i: f"b:{pid}:{cid}:{i}:x", back)
                )
            await callback.answer("🎨 Rangni tanlang")
            return
        if product.sizes and si == "x":
            if msg:
                await msg.edit_reply_markup(
                    reply_markup=picker_kb(product.sizes, lambda j: f"b:{pid}:{cid}:{ci}:{j}", back)
                )
            await callback.answer("📏 O'lchamni tanlang")
            return
        color_ok, color = _pick(product.colors, ci)
        size_ok, size = _pick(product.sizes, si)
        if not (color_ok and size_ok):
            await callback.answer("Ma'lumot yangilandi, qaytadan tanlang", show_alert=True)
            return
        await add_to_cart(session, user_id, pid, color, size)
        card = await build_card(session, user_id, cid, product_id=pid)
    if msg and card:
        await msg.edit_reply_markup(reply_markup=card.markup)
    variant = t.item_variant(color, size)
    await callback.answer("✅ Savatga qo'shildi" + (f" · {variant}" if variant else ""))


@router.callback_query(F.data.startswith("bk:"))
async def on_picker_back(callback: CallbackQuery) -> None:
    async with async_session() as session:
        card = await build_card(
            session,
            callback.from_user.id,
            cb_int(callback, 2),
            product_id=cb_int(callback, 1),
        )
    msg = cb_message(callback)
    if msg and card:
        await msg.edit_reply_markup(reply_markup=card.markup)
    await callback.answer()


@router.callback_query(F.data == "noop")
async def on_noop(callback: CallbackQuery) -> None:
    await callback.answer()
