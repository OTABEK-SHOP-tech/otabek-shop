"""Cart, checkout (phone -> address -> confirm) and the customer's order history."""

import re
from html import escape

from aiogram import Bot, F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message
from sqlalchemy import select

from bekstyle import texts as t
from bekstyle.db import Order, User, async_session, get_setting
from bekstyle.handlers import cb_int, cb_message, menu_for, show_in
from bekstyle.keyboards import cart_kb, inline, phone_kb, reply_kb
from bekstyle.notify import notify_admins_new_order, safe_edit_text
from bekstyle.services import (
    cart_snapshot,
    change_cart_qty,
    clear_cart,
    create_order_from_cart,
    get_cart,
    snapshot_total,
)

router = Router(name="cart")

PHONE_RE = re.compile(r"\+?[0-9][0-9\s\-()]{8,18}")
ADDRESS_MIN, ADDRESS_MAX = 5, 200
ORDERS_SHOWN = 10


class Checkout(StatesGroup):
    phone = State()
    address = State()
    confirm = State()


async def cart_view(user_id: int) -> tuple[str, InlineKeyboardMarkup]:
    async with async_session() as session:
        items = await get_cart(session, user_id)
    if not items:
        return (
            "🛒 <b>Savat bo'sh</b>\n\nKatalogdan o'zingizga yoqqanini tanlang 👇",
            inline([("🛍 Katalog", "cats")]),
        )
    rows = [
        {
            **row,
            "title": row["title"] + ("" if item.product.in_stock else " ⚪️ tugagan"),
        }
        for row, item in zip(cart_snapshot(items), items, strict=True)
    ]
    total = snapshot_total(cart_snapshot([it for it in items if it.product.in_stock]))
    text = f"🛒 <b>Savat</b>\n{t.LINE}\n{t.items_block(rows)}\n{t.LINE}\n💵 Jami: <b>{t.format_price(total)}</b>"
    return text, cart_kb([it.id for it in items])


@router.message(F.text == t.BTN_CART)
async def on_cart(message: Message) -> None:
    if message.from_user:
        text, markup = await cart_view(message.from_user.id)
        await message.answer(text, reply_markup=markup)


@router.callback_query(F.data == "cart")
async def on_cart_button(callback: CallbackQuery) -> None:
    msg = cb_message(callback)
    if msg:
        text, markup = await cart_view(callback.from_user.id)
        await msg.answer(text, reply_markup=markup)
    await callback.answer()


@router.callback_query(F.data.startswith("cq:"))
async def on_cart_qty(callback: CallbackQuery) -> None:
    async with async_session() as session:
        await change_cart_qty(session, callback.from_user.id, cb_int(callback, 1), cb_int(callback, 2))
    await show_in(callback, *await cart_view(callback.from_user.id))


@router.callback_query(F.data == "cclear")
async def on_cart_clear(callback: CallbackQuery) -> None:
    async with async_session() as session:
        await clear_cart(session, callback.from_user.id)
    await show_in(callback, *await cart_view(callback.from_user.id))


@router.callback_query(F.data == "checkout")
async def on_checkout(callback: CallbackQuery, state: FSMContext) -> None:
    async with async_session() as session:
        items = await get_cart(session, callback.from_user.id)
        user = await session.get(User, callback.from_user.id)
    msg = cb_message(callback)
    if not any(it.product.in_stock for it in items) or msg is None:
        await callback.answer("Savatda buyurtma qilinadigan mahsulot yo'q", show_alert=True)
        return
    await state.set_state(Checkout.phone)
    await msg.answer(
        "📱 <b>1/2 · Telefon</b>\nRaqamingizni yuboring yoki yozing: <code>+998 90 123 45 67</code>",
        reply_markup=phone_kb(user.phone if user else None),
    )
    await callback.answer()


async def _save_phone(message: Message, state: FSMContext, raw: str) -> None:
    await state.update_data(phone="+" + re.sub(r"\D", "", raw))
    await state.set_state(Checkout.address)
    await message.answer(
        "📍 <b>2/2 · Manzil</b>\nShahar, tuman va mo'ljal.\n<i>Masalan: Toshkent, Chilonzor, 9-kvartal</i>",
        reply_markup=reply_kb(),
    )


@router.message(Checkout.phone, F.contact)
async def on_phone_contact(message: Message, state: FSMContext) -> None:
    contact = message.contact
    if contact is None or message.from_user is None:
        return
    if contact.user_id and contact.user_id != message.from_user.id:
        await message.answer("🙏 O'zingizning raqamingizni yuboring.")
        return
    await _save_phone(message, state, contact.phone_number)


@router.message(Checkout.phone, F.text)
async def on_phone_text(message: Message, state: FSMContext) -> None:
    raw = (message.text or "").strip()
    if not PHONE_RE.fullmatch(raw):
        await message.answer("⚠️ Raqam noto'g'ri. Masalan: <code>+998 90 123 45 67</code>")
        return
    await _save_phone(message, state, raw)


@router.message(Checkout.address, F.text)
async def on_address(message: Message, state: FSMContext) -> None:
    address = (message.text or "").strip()
    if not ADDRESS_MIN <= len(address) <= ADDRESS_MAX or message.from_user is None:
        await message.answer("⚠️ Manzilni to'liqroq yozing: shahar, tuman, mo'ljal.")
        return
    await state.update_data(address=address)
    async with async_session() as session:
        items = [it for it in await get_cart(session, message.from_user.id) if it.product.in_stock]
    data = await state.get_data()
    snapshot = cart_snapshot(items)
    await state.set_state(Checkout.confirm)
    await message.answer(
        f"🧾 <b>Buyurtmani tasdiqlang</b>\n{t.LINE}\n{t.items_block(snapshot)}\n{t.LINE}\n"
        f"💵 Jami: <b>{t.format_price(snapshot_total(snapshot))}</b>\n"
        f"📱 {data['phone']}\n📍 {escape(address)}\n\n💳 To'lov tafsilotlarini admin yozadi.",
        reply_markup=inline([("✅ Tasdiqlash", "co:yes"), ("❌ Bekor", "co:no")]),
    )


async def _finish(callback: CallbackQuery, state: FSMContext, text: str, extra: str | None = None) -> None:
    await state.clear()
    msg = cb_message(callback)
    if msg:
        await safe_edit_text(msg, text)
        if extra:
            await msg.answer(extra, reply_markup=await menu_for(callback.from_user.id))
    await callback.answer()


@router.callback_query(Checkout.confirm, F.data == "co:yes")
async def on_confirm(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    data = await state.get_data()
    tg_user = callback.from_user
    async with async_session() as session:
        order, dropped = await create_order_from_cart(
            session,
            tg_user.id,
            tg_user.full_name,
            tg_user.username,
            data["phone"],
            data["address"],
        )
        delivery = await get_setting(session, "delivery_text")
        contact = await get_setting(session, "contact_username")
    if order is None:
        await _finish(
            callback,
            state,
            "😕 Savatdagi mahsulotlar tugab qoldi.",
            "👇 Katalogdan boshqasini tanlang.",
        )
        return
    note = f"\n\n⚪️ {dropped} ta tugagan mahsulot buyurtmaga kirmadi." if dropped else ""
    await _finish(
        callback,
        state,
        t.order_text(order.id, order.status, order.items, order.total, order.created_at),
        t.status_message(order.id, order.status, delivery, contact) + note,
    )
    await notify_admins_new_order(bot, order)


@router.callback_query(Checkout.confirm, F.data == "co:no")
async def on_decline(callback: CallbackQuery, state: FSMContext) -> None:
    await _finish(callback, state, "❌ Buyurtma bekor qilindi. Savat saqlanib qoldi.", "👇 Menyu")


@router.callback_query(StateFilter(None), F.data.startswith("co:"))
async def on_stale_confirm(callback: CallbackQuery) -> None:
    await callback.answer("Bu tugma eskirgan. Savatdan qayta buyurtma bering.", show_alert=True)


@router.message(F.text == t.BTN_ORDERS)
async def on_my_orders(message: Message) -> None:
    if message.from_user is None:
        return
    async with async_session() as session:
        orders = (
            await session.scalars(
                select(Order).where(Order.user_id == message.from_user.id).order_by(Order.id.desc()).limit(ORDERS_SHOWN)
            )
        ).all()
    if not orders:
        await message.answer("📦 Hali buyurtma yo'q. 🛍 Katalogdan boshlang!")
        return
    lines = [
        f"<b>#{o.id}</b> · {t.status_label(o.status)} · {t.format_price(o.total)} · {t.format_dt(o.created_at)}"
        for o in orders
    ]
    await message.answer(f"📦 <b>Buyurtmalarim</b>\n{t.LINE}\n" + "\n".join(lines))
