from html import escape
import logging
from aiogram import Router, F
from aiogram.types import (
    InlineQuery,
    InlineQueryResultArticle,
    InputTextMessageContent,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
)
from sqlalchemy import select, or_

from api.config import settings
from api.services.formatters import format_price, calculate_cargo
from bot.loader import bot
from db.models import Product
from db.session import async_session_factory

router = Router(name="inline")
logger = logging.getLogger(__name__)


@router.inline_query()
async def handle_inline_search(inline_query: InlineQuery):
    query_text = inline_query.query.strip().lower()
    clean_search = query_text.replace("#", "")

    async with async_session_factory() as session:
        query = select(Product).where(Product.in_stock == True)
        if clean_search and clean_search not in ["dilemma", "look", "solishtir", "tanlov"]:
            term = f"%{clean_search}%"
            query = query.where(
                or_(
                    Product.title.ilike(term),
                    Product.description.ilike(term),
                    Product.category.ilike(term),
                )
            )
        query = query.limit(15)
        res = await session.execute(query)
        products = res.scalars().all()

    bot_info = await bot.get_me() if bot else None
    bot_username = bot_info.username if bot_info else "moonlight_chinese_bot"

    results = []

    # Feature #2: "Lookni Tanlashda Yordam Ber" (Dilemma Poll Inline Card)
    if len(products) >= 2 and (not clean_search or clean_search in ["dilemma", "look", "solishtir", "tanlov"]):
        p1, p2 = products[0], products[1]
        dilemma_caption = (
            "🤔 <b>Qizlar, qaysi birini olay? Yordam bering! ✨</b>\n\n"
            f"1️⃣ <b>{escape(p1.title)}</b> — {format_price(p1.price)}\n"
            f"2️⃣ <b>{escape(p2.title)}</b> — {format_price(p2.price)}\n\n"
            "<i>Pastdagi tugmalar orqali ovoz bering va eng chiroylisini aniqlaylik:</i>"
        )
        dilemma_markup = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=f"🌸 1-variant (0)",
                        callback_data=f"vote:1:0:0:{p1.id}:{p2.id}"
                    ),
                    InlineKeyboardButton(
                        text=f"✨ 2-variant (0)",
                        callback_data=f"vote:2:0:0:{p1.id}:{p2.id}"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="🛍️ Moonlight Do'konini ochish",
                        url=f"https://t.me/{bot_username}?startapp=dilemma"
                    )
                ]
            ]
        )
        results.append(
            InlineQueryResultArticle(
                id="dilemma_poll_card",
                title="🤔 Dilemma: Qaysi lookni tanlay? (Guruhda so'rovnoma)",
                description=f"1: {p1.title[:20]} VS 2: {p2.title[:20]} — Do'stlaringiz bilan ovoz bering!",
                input_message_content=InputTextMessageContent(
                    message_text=dilemma_caption,
                    parse_mode="HTML"
                ),
                reply_markup=dilemma_markup
            )
        )

    for prod in products:
        cargo = calculate_cargo(prod.weight_grams)
        caption = (
            f"🌙 <b>{escape(prod.title)}</b>\n"
            f"💰 Narxi: <b>{format_price(prod.price)}</b>\n"
            f"📦 Kargo: ~{format_price(cargo)}\n\n"
            f"💌 Buyurtma berish uchun do'konga kiring"
        )

        markup = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🛍️ Do'konda ko'rish",
                        url=f"https://t.me/{bot_username}?startapp=product_{prod.id}",
                    )
                ]
            ]
        )

        results.append(
            InlineQueryResultArticle(
                id=str(prod.id),
                title=f"{prod.title} — {format_price(prod.price)}",
                description=f"#{prod.category} | {prod.description[:60] if prod.description else 'Moonlight Chinese Shop'}",
                input_message_content=InputTextMessageContent(
                    message_text=caption,
                    parse_mode="HTML",
                ),
                reply_markup=markup,
            )
        )

    await inline_query.answer(results=results, cache_time=10, is_personal=False)


@router.callback_query(F.data.startswith("vote:"))
async def handle_dilemma_vote(callback: CallbackQuery):
    """Handles real-time viral interactive poll voting in inline dilemma messages."""
    parts = callback.data.split(":")
    if len(parts) < 6:
        await callback.answer("Ovoz qabul qilindi!")
        return

    choice = parts[1]
    try:
        c1 = int(parts[2])
        c2 = int(parts[3])
    except ValueError:
        c1, c2 = 0, 0

    p1_id, p2_id = parts[4], parts[5]

    if choice == "1":
        c1 += 1
    else:
        c2 += 1

    bot_info = await bot.get_me() if bot else None
    bot_username = bot_info.username if bot_info else "moonlight_chinese_bot"

    new_markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"🌸 1-variant ({c1})",
                    callback_data=f"vote:1:{c1}:{c2}:{p1_id}:{p2_id}"
                ),
                InlineKeyboardButton(
                    text=f"✨ 2-variant ({c2})",
                    callback_data=f"vote:2:{c1}:{c2}:{p1_id}:{p2_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🛍️ Moonlight Do'konini ochish",
                    url=f"https://t.me/{bot_username}?startapp=dilemma"
                )
            ]
        ]
    )

    try:
        await callback.edit_message_reply_markup(reply_markup=new_markup)
        await callback.answer(f"{choice}-variantga ovoz berildi! Rahmat! ✨")
    except Exception:
        await callback.answer("Ovozingiz qo'shildi! ✨")
