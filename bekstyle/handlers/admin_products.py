"""Admin: add-product wizard, product list/management, categories."""

import asyncio
from collections import defaultdict
from html import escape

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message
from sqlalchemy import delete, func, select

from bekstyle import texts as t
from bekstyle.db import CartItem, Category, Product, async_session, get_setting
from bekstyle.handlers import IsAdmin, cb_int, cb_message, menu_for, show_in
from bekstyle.keyboards import grid, inline, main_menu, reply_kb
from bekstyle.notify import post_product_to_channel
from bekstyle.services import (
    PriceInput,
    categories_with_counts,
    margin_som,
    parse_category_input,
    parse_list,
    parse_price_input,
)

router = Router(name="admin_products")
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())

MAX_PHOTOS = 10
PAGE_SIZE = 8
TITLE_MAX = 100
DESCRIPTION_MAX = 800
# Album photos arrive as separate updates handled concurrently; serialize per chat so none is lost.
_photo_locks: defaultdict[int, asyncio.Lock] = defaultdict(asyncio.Lock)


class AddProduct(StatesGroup):
    photos = State()
    title = State()
    category = State()
    price = State()
    colors = State()
    sizes = State()
    description = State()
    confirm = State()


class EditPrice(StatesGroup):
    value = State()


class AddCategory(StatesGroup):
    name = State()


# ---------- pricing helpers ----------
async def _pricing() -> tuple[int, int]:
    async with async_session() as session:
        return int(await get_setting(session, "yuan_rate")), int(await get_setting(session, "markup_percent"))


def _price_prompt(rate: int, markup: int) -> str:
    return (
        "💵 <b>Narx</b>\n"
        "• Pinduoduo narxi yuanda: <code>79¥</code> — bot ustama bilan hisoblaydi\n"
        "• yoki tayyor narx so'mda: <code>189000</code>\n\n"
        f"💱 1¥ = {rate} so'm · 📈 ustama {markup}%"
    )


def _price_summary(price: PriceInput, rate: int) -> str:
    line = f"💵 Sotuv narxi: <b>{t.format_price(price.price)}</b>"
    margin = margin_som(price.price, price.cost_cny, rate)
    if price.cost_cny is not None and margin is not None:
        line += f"\n🇨🇳 Pinduoduo: {price.cost_cny:g}¥ ≈ {t.format_price(round(price.cost_cny * rate))} · foyda ≈ {t.format_price(margin)}"
    return line


# ---------- add-product wizard ----------
@router.callback_query(F.data == "ap:add")
async def on_add_product(callback: CallbackQuery, state: FSMContext) -> None:
    msg = cb_message(callback)
    if msg is None:
        return
    await state.clear()
    await state.set_state(AddProduct.photos)
    await state.update_data(photos=[])
    await msg.answer(
        "➕ <b>Yangi mahsulot · 1/7 · Rasmlar</b>\n"
        f"Rasmlarni ketma-ket yoki albom qilib yuboring (1–{MAX_PHOTOS} ta). Birinchi rasm — muqova.\n"
        f"Tugatgach «{t.BTN_DONE_PHOTOS}» ni bosing.",
        reply_markup=reply_kb(t.BTN_DONE_PHOTOS),
    )
    await callback.answer()


@router.message(AddProduct.photos, F.photo)
async def on_wizard_photo(message: Message, state: FSMContext) -> None:
    if not message.photo:
        return
    async with _photo_locks[message.chat.id]:
        data = await state.get_data()
        photos: list[str] = list(data.get("photos", []))
        if len(photos) >= MAX_PHOTOS:
            if not data.get("limit_warned"):
                await state.update_data(limit_warned=True)
                await message.answer(f"⚠️ Ko'pi bilan {MAX_PHOTOS} ta rasm. Ortiqchasi olinmadi.")
            return
        photos = [*photos, message.photo[-1].file_id]
        await state.update_data(photos=photos)
        group = message.media_group_id
        if group is None:
            await message.answer(f"📸 {len(photos)}/{MAX_PHOTOS} · yana yuboring yoki «{t.BTN_DONE_PHOTOS}»")
        elif data.get("last_group") != group:
            await state.update_data(last_group=group)
            await message.answer(f"📸 Albom qabul qilindi · yana yuboring yoki «{t.BTN_DONE_PHOTOS}»")


@router.message(AddProduct.photos, F.text == t.BTN_DONE_PHOTOS)
async def on_photos_done(message: Message, state: FSMContext) -> None:
    async with _photo_locks[message.chat.id]:
        photos: list[str] = list((await state.get_data()).get("photos", []))
    if not photos:
        await message.answer("⚠️ Kamida 1 ta rasm yuboring.")
        return
    await state.set_state(AddProduct.title)
    await message.answer(
        f"✅ {len(photos)} ta rasm.\n\n✍️ <b>2/7 · Nomi</b>\n<i>Masalan: Oversize futbolka «Essential»</i>",
        reply_markup=reply_kb(),
    )


@router.message(AddProduct.photos)
async def on_photos_other(message: Message) -> None:
    await message.answer(f"📸 Rasm yuboring yoki «{t.BTN_DONE_PHOTOS}» ni bosing.")


@router.message(AddProduct.title, F.text)
async def on_wizard_title(message: Message, state: FSMContext) -> None:
    title = (message.text or "").strip()
    if not 2 <= len(title) <= TITLE_MAX:
        await message.answer(f"⚠️ Nom 2–{TITLE_MAX} belgi bo'lsin.")
        return
    async with async_session() as session:
        cats = (await session.scalars(select(Category).order_by(Category.sort_order, Category.id))).all()
    if not cats:
        await message.answer("⚠️ Avval bo'lim qo'shing: 👑 Admin panel → 🗂 Bo'limlar.")
        return
    await state.update_data(title=title)
    await state.set_state(AddProduct.category)
    await message.answer(
        "🗂 <b>3/7 · Bo'lim</b>",
        reply_markup=grid([(f"{c.emoji} {c.name}", f"wcat:{c.id}") for c in cats], 2),
    )


@router.callback_query(AddProduct.category, F.data.startswith("wcat:"))
async def on_wizard_category(callback: CallbackQuery, state: FSMContext) -> None:
    msg = cb_message(callback)
    if msg is None:
        return
    await state.update_data(category_id=cb_int(callback, 1))
    await state.set_state(AddProduct.price)
    await msg.answer("4/7 · " + _price_prompt(*await _pricing()), reply_markup=reply_kb())
    await callback.answer()


@router.message(AddProduct.price, F.text)
async def on_wizard_price(message: Message, state: FSMContext) -> None:
    rate, markup = await _pricing()
    price = parse_price_input(message.text or "", rate, markup)
    if price is None:
        await message.answer("⚠️ Tushunmadim. Masalan: <code>79¥</code> yoki <code>189000</code>")
        return
    await state.update_data(price=price.price, cost_cny=price.cost_cny)
    await state.set_state(AddProduct.colors)
    await message.answer(
        f"{_price_summary(price, rate)}\n\n🎨 <b>5/7 · Ranglar</b> (vergul bilan)\n<i>Masalan: Qora, Oq, Yashil</i>",
        reply_markup=reply_kb(t.BTN_SKIP),
    )


@router.message(AddProduct.colors, F.text)
async def on_wizard_colors(message: Message, state: FSMContext) -> None:
    colors = [] if message.text == t.BTN_SKIP else parse_list(message.text or "")
    await state.update_data(colors=colors)
    await state.set_state(AddProduct.sizes)
    await message.answer(
        "📏 <b>6/7 · O'lchamlar</b>\nTayyor variantni tanlang yoki vergul bilan yozing.",
        reply_markup=reply_kb(*t.SIZE_PRESETS, t.BTN_SKIP),
    )


@router.message(AddProduct.sizes, F.text)
async def on_wizard_sizes(message: Message, state: FSMContext) -> None:
    sizes = [] if message.text == t.BTN_SKIP else parse_list(message.text or "")
    await state.update_data(sizes=sizes)
    await state.set_state(AddProduct.description)
    await message.answer(
        "📝 <b>7/7 · Tavsif</b> (mato, fason, maslahat)\n<i>Masalan: 100% paxta, oversize fit. Bo'yingizga mos o'lcham oling.</i>",
        reply_markup=reply_kb(t.BTN_SKIP),
    )


@router.message(AddProduct.description, F.text)
async def on_wizard_description(message: Message, state: FSMContext) -> None:
    description = "" if message.text == t.BTN_SKIP else (message.text or "").strip()[:DESCRIPTION_MAX]
    await state.update_data(description=description)
    data = await state.get_data()
    async with async_session() as session:
        delivery = await get_setting(session, "delivery_text")
    await state.set_state(AddProduct.confirm)
    await message.answer(
        f"👀 <b>Ko'rinishi</b> · 📸 {len(data['photos'])} ta rasm",
        reply_markup=main_menu(True),
    )
    await message.answer_photo(
        data["photos"][0],
        caption=t.product_caption(
            data["title"],
            data["price"],
            data["colors"],
            data["sizes"],
            description,
            delivery,
            True,
        ),
        reply_markup=inline([("✅ Saqlash", "wsave"), ("❌ Bekor", "wcancel")]),
    )


@router.callback_query(AddProduct.confirm, F.data == "wsave")
async def on_wizard_save(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    msg = cb_message(callback)
    async with async_session() as session:
        product = Product(
            title=data["title"],
            description=data.get("description", ""),
            price=data["price"],
            cost_cny=data.get("cost_cny"),
            category_id=data["category_id"],
            photos=data["photos"],
            colors=data.get("colors", []),
            sizes=data.get("sizes", []),
            in_stock=True,
        )
        session.add(product)
        await session.commit()
        product_id = product.id
    await state.clear()
    if msg:
        await msg.edit_reply_markup(reply_markup=None)
        await msg.answer(
            f"✅ <b>#{product_id} saqlandi</b> — katalogda ko'rinadi.\nKanalga ham joylaymi?",
            reply_markup=inline(
                [("📢 Kanalga joylash", f"apc:{product_id}")],
                [("➕ Yana qo'shish", "ap:add"), ("📦 Mahsulotlar", "apl:0")],
            ),
        )
    await callback.answer("Saqlandi ✅")


@router.callback_query(F.data.in_({"wsave", "wcancel"}))
async def on_wizard_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    """wcancel, or a stale wsave pressed after the wizard was already closed."""
    await state.clear()
    msg = cb_message(callback)
    if msg:
        await msg.edit_reply_markup(reply_markup=None)
    await callback.answer("Bekor qilindi")


# ---------- product list & management ----------
@router.callback_query(F.data.startswith("apl:"))
async def on_product_list(callback: CallbackQuery) -> None:
    page = max(0, cb_int(callback, 1))
    async with async_session() as session:
        total = int(await session.scalar(select(func.count(Product.id))) or 0)
        products = (
            await session.scalars(select(Product).order_by(Product.id.desc()).offset(page * PAGE_SIZE).limit(PAGE_SIZE))
        ).all()
    rows = [
        [
            (
                f"{'🟢' if p.in_stock else '⚪️'} {t.clip(p.title, 26)} · {t.format_price(p.price)}",
                f"apv:{p.id}",
            )
        ]
        for p in products
    ]
    nav = ([("◀️", f"apl:{page - 1}")] if page > 0 else []) + (
        [("▶️", f"apl:{page + 1}")] if (page + 1) * PAGE_SIZE < total else []
    )
    if nav:
        rows.append(nav)
    rows.append([("➕ Qo'shish", "ap:add"), ("⬅️ Menyu", "a:menu")])
    header = f"📦 <b>Mahsulotlar</b> · {total} ta\n🟢 sotuvda · ⚪️ tugagan" if total else "📦 Hali mahsulot yo'q."
    await show_in(callback, header, inline(*rows))


async def product_admin_view(
    product_id: int,
) -> tuple[str, InlineKeyboardMarkup] | None:
    async with async_session() as session:
        p = await session.get(Product, product_id)
        rate = int(await get_setting(session, "yuan_rate"))
    if p is None:
        return None
    lines = [
        f"#{p.id} · <b>{escape(p.title)}</b>",
        t.LINE,
        f"🗂 {p.category.emoji} {escape(p.category.name)}",
        _price_summary(PriceInput(p.price, p.cost_cny), rate),
        *t.attrs_lines(p.colors, p.sizes),
        f"📸 {len(p.photos)} ta rasm · 📢 kanalda: {'ha' if p.channel_message_id else 'yoʻq'}",
        f"Holat: {'🟢 Sotuvda' if p.in_stock else '⚪️ Tugagan'}",
    ]
    markup = inline(
        [
            (
                "⚪️ Tugadi deb belgilash" if p.in_stock else "🟢 Sotuvga qaytarish",
                f"apt:{p.id}",
            )
        ],
        [("💵 Narxni o'zgartirish", f"ape:{p.id}"), ("📢 Kanalga", f"apc:{p.id}")],
        [("🗑 O'chirish", f"apd:{p.id}"), ("⬅️ Ro'yxat", "apl:0")],
    )
    return "\n".join(lines), markup


async def _show_product(callback: CallbackQuery, product_id: int) -> None:
    view = await product_admin_view(product_id)
    if view is None:
        await callback.answer("Mahsulot topilmadi", show_alert=True)
        return
    await show_in(callback, *view)


@router.callback_query(F.data.startswith("apv:"))
async def on_product_view(callback: CallbackQuery) -> None:
    await _show_product(callback, cb_int(callback, 1))


@router.callback_query(F.data.startswith("apt:"))
async def on_toggle_stock(callback: CallbackQuery) -> None:
    product_id = cb_int(callback, 1)
    async with async_session() as session:
        product = await session.get(Product, product_id)
        if product:
            product.in_stock = not product.in_stock
            await session.commit()
    await _show_product(callback, product_id)


@router.callback_query(F.data.startswith("ape:"))
async def on_edit_price(callback: CallbackQuery, state: FSMContext) -> None:
    msg = cb_message(callback)
    if msg is None:
        return
    await state.set_state(EditPrice.value)
    await state.update_data(product_id=cb_int(callback, 1))
    await msg.answer(_price_prompt(*await _pricing()), reply_markup=reply_kb())
    await callback.answer()


@router.message(EditPrice.value, F.text)
async def on_edit_price_value(message: Message, state: FSMContext) -> None:
    rate, markup = await _pricing()
    price = parse_price_input(message.text or "", rate, markup)
    if price is None:
        await message.answer("⚠️ Masalan: <code>79¥</code> yoki <code>189000</code>")
        return
    product_id = int((await state.get_data())["product_id"])
    async with async_session() as session:
        product = await session.get(Product, product_id)
        if product:
            product.price = price.price
            if price.cost_cny is not None:  # a plain so'm price keeps the known Pinduoduo cost
                product.cost_cny = price.cost_cny
            await session.commit()
    await state.clear()
    await message.answer("✅ Narx yangilandi.", reply_markup=await menu_for(message.chat.id))
    view = await product_admin_view(product_id)
    if view:
        await message.answer(view[0], reply_markup=view[1])


@router.callback_query(F.data.startswith("apc:"))
async def on_post_channel(callback: CallbackQuery, bot: Bot) -> None:
    async with async_session() as session:
        product = await session.get(Product, cb_int(callback, 1))
    msg = cb_message(callback)
    if product is None or msg is None:
        await callback.answer("Mahsulot topilmadi", show_alert=True)
        return
    await callback.answer("⏳ Joylanmoqda…")
    _, result = await post_product_to_channel(bot, product)
    await msg.answer(f"📢 #{product.id}: {escape(result)}")


@router.callback_query(F.data.startswith("apd:"))
async def on_delete_ask(callback: CallbackQuery) -> None:
    product_id = cb_int(callback, 1)
    await show_in(
        callback,
        f"🗑 #{product_id} o'chirilsinmi? Savatlardan ham olib tashlanadi, buyurtmalar tarixi qoladi.",
        inline(
            [
                ("✅ Ha, o'chirish", f"apdy:{product_id}"),
                ("⬅️ Yo'q", f"apv:{product_id}"),
            ]
        ),
    )


@router.callback_query(F.data.startswith("apdy:"))
async def on_delete_yes(callback: CallbackQuery) -> None:
    product_id = cb_int(callback, 1)
    async with async_session() as session:
        await session.execute(delete(CartItem).where(CartItem.product_id == product_id))
        await session.execute(delete(Product).where(Product.id == product_id))
        await session.commit()
    await show_in(
        callback,
        f"🗑 #{product_id} o'chirildi.",
        inline([("📦 Mahsulotlar", "apl:0"), ("⬅️ Menyu", "a:menu")]),
    )


# ---------- categories ----------
@router.callback_query(F.data == "a:cats")
async def on_categories(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    async with async_session() as session:
        rows = await categories_with_counts(session, in_stock_only=False)
    pairs = [(f"{cat.emoji} {cat.name} · {count}", f"acv:{cat.id}") for cat, count in rows]
    await show_in(
        callback,
        "🗂 <b>Bo'limlar</b>\nO'chirish uchun bo'limni tanlang (faqat bo'sh bo'lim o'chadi).",
        grid(pairs, 2, [("➕ Bo'lim qo'shish", "ac:add"), ("⬅️ Menyu", "a:menu")]),
    )


@router.callback_query(F.data.startswith("acv:"))
async def on_category_view(callback: CallbackQuery) -> None:
    category_id = cb_int(callback, 1)
    async with async_session() as session:
        category = await session.get(Category, category_id)
        count = int(await session.scalar(select(func.count(Product.id)).where(Product.category_id == category_id)) or 0)
    if category is None:
        await callback.answer("Bo'lim topilmadi", show_alert=True)
        return
    await show_in(
        callback,
        f"🗂 {category.emoji} <b>{escape(category.name)}</b> · {count} ta mahsulot",
        inline([("🗑 O'chirish", f"acd:{category_id}"), ("⬅️ Bo'limlar", "a:cats")]),
    )


@router.callback_query(F.data.startswith("acd:"))
async def on_category_delete(callback: CallbackQuery, state: FSMContext) -> None:
    category_id = cb_int(callback, 1)
    async with async_session() as session:
        if await session.scalar(select(Product.id).where(Product.category_id == category_id).limit(1)):
            await callback.answer("⛔ Bo'limda mahsulot bor. Avval ularni o'chiring.", show_alert=True)
            return
        await session.execute(delete(Category).where(Category.id == category_id))
        await session.commit()
    await on_categories(callback, state)


@router.callback_query(F.data == "ac:add")
async def on_category_add(callback: CallbackQuery, state: FSMContext) -> None:
    msg = cb_message(callback)
    if msg is None:
        return
    await state.set_state(AddCategory.name)
    await msg.answer(
        "➕ Bo'lim nomi, oldida emoji bilan:\n<i>Masalan: 🩳 Shortilar</i>",
        reply_markup=reply_kb(),
    )
    await callback.answer()


@router.message(AddCategory.name, F.text)
async def on_category_name(message: Message, state: FSMContext) -> None:
    parsed = parse_category_input(message.text or "")
    if parsed is None:
        await message.answer("⚠️ Nom 2–40 belgi bo'lsin. Masalan: <code>🩳 Shortilar</code>")
        return
    emoji, name = parsed
    async with async_session() as session:
        if await session.scalar(select(Category.id).where(func.lower(Category.name) == name.lower())):
            await message.answer("ℹ️ Bunday bo'lim bor. Boshqa nom yozing.")
            return
        session.add(Category(name=name, emoji=emoji))
        await session.commit()
    await state.clear()
    await message.answer(
        f"✅ {emoji} {escape(name)} qo'shildi.",
        reply_markup=await menu_for(message.chat.id),
    )
