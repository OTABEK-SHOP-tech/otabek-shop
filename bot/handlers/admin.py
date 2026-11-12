from html import escape
import os
import re
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path

from aiogram import Router, F
from datetime import datetime, timezone
from aiogram.filters import Command, CommandObject, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardRemove,
    FSInputFile,
    WebAppInfo,
)
from sqlalchemy import select, func, desc, delete

import asyncio
from api.config import settings
from api.services.formatters import (
    format_price,
    calculate_cargo,
    parse_channel_post,
    build_channel_caption,
    parse_sizes,
    format_sizes_display,
    calculate_retail_price,
    calculate_margin_percent,
)
from api.services.telegram_fetcher import (
    extract_telegram_post_links,
    fetch_telegram_post_embed,
    TG_POST_LINK_RE,
)
from bot.keyboards.reply import get_admin_main_keyboard, get_main_reply_keyboard
from bot.services.channel_post import post_product_to_channel
from bot.services.ownership import claim_ownership, create_owner_invite
from bot.services.premium_emojis import (
    upgrade_to_premium_emojis,
    PREMIUM_BTN_BAG_ID,
    PREMIUM_BTN_STAR_ID,
)
from db.models import Admin, Product, Category, Review, Order, User, Setting
from db.session import async_session_factory

router = Router(name="admin")
logger = logging.getLogger(__name__)


# FSM States for Add Product Wizard
class ProductWizard(StatesGroup):
    photos = State()
    title = State()
    price = State()
    category = State()
    sizes = State()
    colors = State()
    weight = State()
    description = State()
    confirm = State()


# FSM States for Add Admin & Broadcast
class CategoryWizard(StatesGroup):
    waiting_for_name = State()
    waiting_for_emoji = State()


class AdminSettingsState(StatesGroup):
    waiting_for_owner_forward = State()
    waiting_for_admin_forward = State()
    waiting_for_broadcast_text = State()


async def is_user_admin(user_id: int) -> bool:
    if settings.DEV_ADMIN_ID and user_id == settings.DEV_ADMIN_ID:
        return True
    async with async_session_factory() as session:
        res = await session.execute(select(Admin).where(Admin.telegram_id == user_id))
        return res.scalars().first() is not None


async def admin_only(event: CallbackQuery) -> bool:
    return event.from_user is not None and await is_user_admin(event.from_user.id)


async def is_admin_message(message: Message) -> bool:
    user_id = message.from_user.id if message.from_user else 0
    return await is_user_admin(user_id)


# All buttons in this router are admin-only (messages are checked in /admin and the forward handler;
# wizard states are only reachable from admin buttons).
router.callback_query.filter(admin_only)


async def _claim_ownership_helper(message: Message, user_id: int, code: str) -> bool:
    """Returns False when the code is not a valid claim (caller continues as a normal user)."""
    async with async_session_factory() as session:
        result = await claim_ownership(
            session, code, user_id, message.from_user.full_name or "Owner", message.from_user.username
        )
    if result == "already_owner":
        await message.answer("🌸 Siz allaqachon do'kon egasisiz! /admin buyrug'ini bosing.")
        return True
    if result == "invalid":
        return False

    owner_welcome = (
        "🌸 <b>Bu do'kon endi sizniki / This shop is now yours</b> 🎀\n\n"
        "Tabriklaymiz! Siz <b>Moonlight Chinese Shop</b>ning rasmiy egasi etib tayinlandingiz.\n\n"
        "✨ <b>Qisqa qo'llanma (3 ta qadam):</b>\n"
        "1️⃣ <b>Yangi mahsulot:</b> /admin buyrug'ini bosing yoki Mini App ichidagi 👑 Admin tugmasidan foydalaning.\n"
        "2️⃣ <b>Kanalni ulash:</b> Botni o'z kanalingizga admin qilib qo'shing — bot avtomatik aniqlaydi va tasdiqlashingiz bilan ulaydi.\n"
        "3️⃣ <b>Buyurtmalar:</b> Mijozlar do'kondan buyurtma berishi bilan bu yerga chiroyli xabar bo'lib keladi.\n\n"
        "Boshqaruv menyusini ochish uchun <b>/admin</b> buyrug'ini bosing! 💗"
    )
    await message.answer(owner_welcome, reply_markup=get_admin_main_keyboard())
    return True


@router.message(Command("admin"))
async def handle_admin_command(message: Message, state: FSMContext, command: CommandObject = None):
    await state.clear()
    user_id = message.from_user.id
    raw_args = (command.args or "").strip() if command else ""

    # Support /admin <secret_code> or /admin claim_<secret_code>
    if raw_args:
        clean_code = raw_args[6:] if raw_args.startswith("claim_") else raw_args
        if await _claim_ownership_helper(message, user_id, clean_code):
            return

    if not await is_user_admin(user_id):
        async with async_session_factory() as session:
            res_owner = await session.execute(select(Admin).where(Admin.role == "owner"))
            has_owner = res_owner.scalars().first() is not None

        if not has_owner:
            # Never reveal the setup code here: anyone can send /admin.
            await message.answer(
                "🌸 <b>Do'kon hali egasiga biriktirilmagan.</b>\n\n"
                "Do'kon egasi maxsus havola orqali biriktiriladi 💗"
            )
        else:
            await message.answer("⛔ Kechirasiz, sizda admin huquqi yo'q.")
        return

    welcome_text = (
        "👑 <b>Moonlight Chinese Shop — Admin Paneli</b> 🌸\n\n"
        "Quyidagi bo'limlardan birini tanlang yoki kanaldagi istalgan postni bu yerga <b>forward</b> qiling (sehrli tezkor import ✨):"
    )
    await message.answer(welcome_text, reply_markup=get_admin_main_keyboard())


# Direct text handler if owner sends setup code as plain text
@router.message(F.text.in_([settings.OWNER_SETUP_CODE, f"claim_{settings.OWNER_SETUP_CODE}"]))
async def handle_direct_setup_code(message: Message, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    code = message.text.strip()
    if not await _claim_ownership_helper(message, user_id, code[6:] if code.startswith("claim_") else code):
        await message.answer("❌ Bu kod yaroqsiz yoki allaqachon ishlatilgan.")


# Cancel command
@router.message(Command("cancel"))
@router.message(F.text.lower() == "/cancel")
@router.message(F.text == "❌ Bekor qilish")
async def handle_cancel_wizard(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("❌ Jarayon bekor qilindi.", reply_markup=get_main_reply_keyboard())
    await message.answer("👑 Admin menyusi:", reply_markup=get_admin_main_keyboard())


# ==================== MAGIC INGESTION: FORWARDS, ALBUMS, LINKS & TEXT ====================
import time

_media_group_buffer: Dict[str, Dict[str, Any]] = {}
_processed_media_groups: Dict[str, float] = {}


CHINESE_MARKET_DOMAINS = (
    "yangkeduo.com",
    "pinduoduo.com",
    "taobao.com",
    "tb.cn",
    "1688.com",
    "dewu.com",
    "poizon.com",
    "aliexpress",
)


def is_importable_message(message: Message) -> bool:
    """Detects if message is a candidate for product import or review import."""
    text = (message.caption or message.text or "").strip()
    if text.startswith("/"):
        return False

    # 1. Any photo/screenshot sent by admin is candidate for product import
    if message.photo:
        return True

    # 2. Forwarded from channel / user / chat
    if (
        getattr(message, "forward_origin", None) is not None
        or getattr(message, "forward_from_chat", None) is not None
        or getattr(message, "forward_date", None) is not None
    ):
        return True

    # 3. Contains Telegram post link
    if TG_POST_LINK_RE.search(text) or "@" in text:
        if extract_telegram_post_links(text):
            return True

    # 4. Contains Chinese marketplace link (Pinduoduo, 1688, Taobao, Poizon)
    if any(domain in text.lower() for domain in CHINESE_MARKET_DOMAINS):
        return True

    # 5. Contains hashtag and price keywords / currency / numbers
    if "#" in text and re.search(r"(?:narxi?|narx|so['’`]?m|som|цена|price|\d{4,}|9\d\s*k|yuan|юань|rmb|[¥￥元])", text, re.IGNORECASE):
        return True

    # 6. Price keywords or Chinese currency in text
    if re.search(r"(?:yuan|юань|rmb|[¥￥元]|\b\d{4,}\s*(?:so['’`]?m|som))", text, re.IGNORECASE):
        return True

    return False


async def show_product_import_summary(message: Message, state: FSMContext) -> None:
    """Builds and shows the final preview card before channel posting."""
    data = await state.get_data()
    photos = data.get("photos", [])
    cat_slug = (data.get("category") or "kiyim").lower().replace("#", "").strip()
    title = data.get("title") or f"{cat_slug.capitalize()} 🌸"
    source_price = data.get("source_price", 0)
    retail_price = data.get("price", 0)
    margin_percent = data.get("margin_percent", 30)
    sizes = data.get("sizes", [])
    colors = data.get("colors", [])
    source_label = data.get("source_label", "Mahsulot importi")

    sizes_display = format_sizes_display(sizes) if sizes else "Standart"
    colors_display = ", ".join(colors) if colors else "Standart"
    source_price_str = format_price(source_price) if source_price else "Aniqlanmadi"
    retail_price_str = format_price(retail_price) if retail_price else "Aniqlanmadi"
    margin_str = f"+{int(margin_percent)}%" if margin_percent else "+30%"

    summary = (
        f"✨ <b>{source_label}: Mahsulot ma'lumotlari tayyor!</b> 🌸\n\n"
        f"🏷️ <b>Kategoriya:</b> #{cat_slug}\n"
        f"🌸 <b>Nomi:</b> {escape(title)}\n"
        f"📥 <b>Asl narxi (ta'minotchi):</b> {source_price_str}\n"
        f"💰 <b>Sotuv narxi ({margin_str} foyda):</b> <b>{retail_price_str}</b>\n"
        f"🌸 <b>Kargo tariflari (har 100g uchun alohida):</b>\n"
        f"  ✈️ <b>AVIA:</b> 14.000 so'm / 100g (7–9 kun)\n"
        f"  🚗 <b>AVTO:</b> 10.000 so'm / 100g (14–18 kun)\n"
        f"🐾 <b>O'lchamlar (Razmer):</b> {escape(sizes_display)}\n"
        f"🎨 <b>Ranglar (Colors):</b> {escape(colors_display)}\n"
        f"📸 <b>Rasmlar:</b> {len(photos)} ta\n\n"
        f"<i>Saqlash tugmasini bossangiz, mahsulot do'konga qo'shiladi va avtomatik Moonlight kanaliga premium stikerlar bilan joylanadi.</i>"
    )

    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ To'g'ri, saqlash & kanalga joylash",
                    callback_data="wizard_save_fast",
                    icon_custom_emoji_id=PREMIUM_BTN_BAG_ID,
                    style="primary",
                ),
            ],
            [
                InlineKeyboardButton(text="✏️ O'zgartirish", callback_data="admin_add_product"),
                InlineKeyboardButton(text="❌ Bekor qilish", callback_data="admin_cancel"),
            ]
        ]
    )
    # Remove reply keyboard if active and show inline summary
    await message.answer("✅ <i>Ma'lumotlar qabul qilindi!</i>", reply_markup=ReplyKeyboardRemove())
    await message.answer(upgrade_to_premium_emojis(summary), reply_markup=markup)


async def process_product_import(
    message: Message,
    state: FSMContext,
    raw_text: str,
    photos: List[str],
    source_label: str = "Sehrli import",
):
    # Check if this is a review screenshot (#отзыв)
    if photos and ("#отзыв" in raw_text.lower() or "fikr" in raw_text.lower() or "rahmat" in raw_text.lower()):
        customer_name = (
            getattr(message, "forward_sender_name", None)
            or (message.from_user.full_name if message.from_user else "Mijoz 💌")
        )
        async with async_session_factory() as session:
            rev = Review(
                customer_name=customer_name,
                text=raw_text.replace("#отзыв", "").strip() or "Mijoz fikri 🌸",
                photos=photos,
                approved=True,
            )
            session.add(rev)
            await session.commit()
        await message.answer("⭐ <b>Mijoz fikri (#отзыв) avtomatik saqlandi va tasdiqlandi!</b> 🌸")
        return

    # Check for Chinese marketplace links without photos (e.g. Pinduoduo / Yangkeduo)
    if not photos and any(domain in raw_text.lower() for domain in CHINESE_MARKET_DOMAINS):
        platform_name = (
            "Pinduoduo (Yang Ke Duo) 🇨🇳"
            if "yangkeduo" in raw_text.lower() or "pinduoduo" in raw_text.lower()
            else (
                "1688 (Alibaba) 🇨🇳"
                if "1688" in raw_text.lower()
                else (
                    "Taobao 🇨🇳"
                    if "taobao" in raw_text.lower() or "tb.cn" in raw_text.lower()
                    else "Xitoy savdo platformasi 🇨🇳"
                )
            )
        )
        m_goods = re.search(r"(?:goods_id|id)=(\d+)|ps=([A-Za-z0-9]+)", raw_text, re.IGNORECASE)
        ref_id = (m_goods.group(1) or m_goods.group(2)) if m_goods else "Aniqlangan"

        guide_msg = (
            f"🌸 <b>{platform_name} tovar havolasi qabul qilindi!</b> ✨\n\n"
            f"🆔 <b>Mahsulot kodi / ID:</b> <code>{ref_id}</code>\n\n"
            f"ℹ️ <i>Eslatma: Pinduoduo va Xitoy ilovalari o'z ichki tizimida bo'lgani sababli, tovar rasmi va narxini tashqi botlar to'g'ridan-to'g'ri o'qiy olmaydi (login talab qiladi).</i>\n\n"
            f"📸 <b>Ushbu tovarni do'konga qo'shish va kanalga chiqarish uchun:</b>\n"
            f"1. Pinduoduo ilovasidan mahsulot <b>rasmini (yoki skrinshotini)</b> ushbu botga yuboring.\n"
            f"2. Tagiga esa Xitoydagi narxini yozing (masalan: <code>28 yuan</code> yoki <code>¥35</code>) yoki so'mdagi narxini <code>50.000 so'm</code>.\n\n"
            f"💰 Bot avtomatik ravishda Yuanni so'mga o'girib, <b>30% foyda</b> qo'shadi, <b>AVTO (10.000 so'm)</b> va <b>AVIA (14.000 so'm)</b> kargo tariflarini biriktirib, <b>Premium stikerlar</b> bilan kanalga tayyorlab beradi! 💌"
        )
        markup = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="➕ Qo'lda tovar qo'shish", callback_data="admin_add_product"),
                ]
            ]
        )
        await message.answer(upgrade_to_premium_emojis(guide_msg), reply_markup=markup)
        return

    # 1. Check if text contains Telegram post link
    tg_links = extract_telegram_post_links(raw_text)
    if tg_links and not photos:
        link_info = tg_links[0]
        if link_info["is_private"]:
            await message.answer(
                "⚠️ <b>Yopiq (shaxsiy) kanal havolasi aniqlandi.</b>\n\n"
                "Telegram cheklovlari sababli yopiq kanal havolasidan to'g'ridan-to'g'ri yuklab bo'lmaydi.\n"
                "Iltimos, ushbu postni o'sha kanaldan to'g'ridan-to'g'ri bu yerga <b>forward</b> qiling yoki rasmi bilan matnini yuboring 🌸"
            )
            return

        status_msg = await message.answer("🔄 <b>Havola tahlil qilinmoqda va rasmlar yuklanmoqda...</b>")
        embed_data = await fetch_telegram_post_embed(link_info["chat_ref"], link_info["message_id"])
        try:
            await status_msg.delete()
        except Exception:
            pass

        if not embed_data["success"]:
            await message.answer(
                f"⚠️ <b>Havoladan ma'lumot yuklab bo'lmadi:</b>\n{embed_data.get('error')}\n\n"
                "Iltimos, postni to'g'ridan-to'g'ri botga <b>forward</b> qiling yoki matn/rasmlarni yuboring 🌸"
            )
            return

        raw_text = embed_data["raw_text"] or raw_text
        photos = embed_data["photos"] or photos
        source_label = f"Havola orqali import (@{link_info['chat_ref']}/{link_info['message_id']})"

    # 2. Parse product channel post with 25%-35% profit margin
    parsed = parse_channel_post(raw_text, apply_margin=True)
    source_price = parsed["source_price"]
    retail_price = parsed["retail_price"]
    margin_percent = parsed["margin_percent"]
    sizes = parsed["sizes"]
    colors = parsed.get("colors", [])
    cargo_rate = parsed.get("cargo_rate", 12000)
    cat_slug = parsed["category"] or "kiyim"
    title = parsed["title"] or f"{cat_slug.capitalize()} 🌸"

    await state.update_data(
        photos=photos,
        title=title,
        price=retail_price,
        source_price=source_price,
        margin_percent=margin_percent,
        old_price=parsed.get("old_price"),
        category=cat_slug,
        sizes=sizes,
        colors=colors,
        weight_grams=parsed.get("weight_grams"),
        cargo_rate=cargo_rate,
        description=raw_text,
        source_label=source_label,
    )

    # If price was not detected: prompt for price
    if not retail_price:
        await state.set_state(ProductWizard.price)
        await message.answer(
            "💰 <b>1-qadam: Mahsulot narxini kiriting:</b>\n"
            "(Xitoydagi narxi: <code>35 yuan</code> yoki so'mda: <code>95.000 so'm</code>)\n\n"
            "<i>Bot avtomatik 25%-35% foyda va kargo hisoblaydi ✨</i>",
            reply_markup=ReplyKeyboardMarkup(
                keyboard=[[KeyboardButton(text="❌ Bekor qilish")]],
                resize_keyboard=True,
            ),
        )
        return

    # If sizes were not detected: prompt for sizes
    if not sizes:
        await state.set_state(ProductWizard.sizes)
        await message.answer(
            "🐾 <b>2-qadam: Mahsulot razmerlarini kiriting:</b>\n"
            "(Masalan: <code>S-2XL</code> yoki <code>S, M, L</code> yoki 'Standart' tugmasini bosing):",
            reply_markup=ReplyKeyboardMarkup(
                keyboard=[
                    [KeyboardButton(text="Standart 🌸")],
                    [KeyboardButton(text="S, M, L"), KeyboardButton(text="S-2XL")],
                    [KeyboardButton(text="❌ Bekor qilish")],
                ],
                resize_keyboard=True,
            ),
        )
        return

    # If colors were not detected: prompt for colors
    if not colors:
        await state.set_state(ProductWizard.colors)
        await message.answer(
            "🎨 <b>3-qadam: Mahsulot ranglarini kiriting:</b>\n"
            "(Masalan: <code>Oq, Qora, Pushti</code> yoki 'Rasmda ko'rsatilgan' tugmasini bosing):",
            reply_markup=ReplyKeyboardMarkup(
                keyboard=[
                    [KeyboardButton(text="Rasmda ko'rsatilgan (Standart) 🌸")],
                    [KeyboardButton(text="Oq, Qora"), KeyboardButton(text="Oq, Qora, Pushti")],
                    [KeyboardButton(text="❌ Bekor qilish")],
                ],
                resize_keyboard=True,
            ),
        )
        return

    # All information present -> show final summary card directly
    await show_product_import_summary(message, state)


@router.message(StateFilter(None, ProductWizard.photos), is_admin_message, is_importable_message)
async def handle_importable_post(message: Message, state: FSMContext):
    user_id = message.from_user.id if message.from_user else 0
    if not await is_user_admin(user_id):
        return

    # Check if admin is currently in the manual photo upload wizard (ProductWizard.photos)
    current_state = await state.get_state()
    if current_state == ProductWizard.photos.state:
        text = (message.caption or message.text or "").strip()
        is_fwd = bool(
            getattr(message, "forward_origin", None)
            or getattr(message, "forward_from_chat", None)
            or getattr(message, "forward_date", None)
        )
        has_link = bool(extract_telegram_post_links(text) or any(d in text.lower() for d in CHINESE_MARKET_DOMAINS))
        has_price = bool(re.search(r"(?:yuan|юань|rmb|[¥￥元]|\b\d{4,}\s*(?:so['’`]?m|som))", text, re.IGNORECASE))
        # If it's a plain photo upload without import signals or media group, delegate to wizard photo collector
        if not is_fwd and not has_link and not has_price and not getattr(message, "media_group_id", None):
            await process_wizard_photo(message, state)
            return

    # Handle Media Group (Photo Album)
    mg_id = getattr(message, "media_group_id", None)
    if mg_id:
        now = time.time()
        # Clean up processed older than 60s
        for k in list(_processed_media_groups.keys()):
            if now - _processed_media_groups[k] > 60:
                _processed_media_groups.pop(k, None)

        if mg_id in _processed_media_groups:
            return

        if mg_id not in _media_group_buffer:
            _media_group_buffer[mg_id] = {
                "photos": [message.photo[-1].file_id] if message.photo else [],
                "text": message.caption or message.text or "",
                "message": message,
            }
            # Wait for all parts of the album to arrive
            await asyncio.sleep(0.6)
            buf = _media_group_buffer.pop(mg_id, None)
            if not buf:
                return
            _processed_media_groups[mg_id] = time.time()
            await process_product_import(
                message=buf["message"],
                state=state,
                raw_text=buf["text"],
                photos=buf["photos"],
                source_label="Sehrli import (Albom)",
            )
            return
        else:
            # Subsequent album items
            if message.photo:
                _media_group_buffer[mg_id]["photos"].append(message.photo[-1].file_id)
            if message.caption and not _media_group_buffer[mg_id]["text"]:
                _media_group_buffer[mg_id]["text"] = message.caption
            return

    # Single message (photo, text, or forward)
    photos = [message.photo[-1].file_id] if message.photo else []
    raw_text = message.caption or message.text or ""
    is_fwd = bool(
        getattr(message, "forward_origin", None)
        or getattr(message, "forward_from_chat", None)
        or getattr(message, "forward_date", None)
    )
    source_label = "Kanaldan forward import" if is_fwd else "Sehrli import"
    await process_product_import(
        message=message,
        state=state,
        raw_text=raw_text,
        photos=photos,
        source_label=source_label,
    )


# ==================== ADD PRODUCT WIZARD (FSM) ====================
@router.callback_query(F.data == "admin_add_product")
async def start_add_product_wizard(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await state.set_state(ProductWizard.photos)
    await state.update_data(photos=[])

    msg = (
        "🌸 <b>Yangi mahsulot qo'shish — 1/8 qadam</b>\n\n"
        "Mahsulot rasmini (yoki 1 tadan 10 tagacha rasmlarni) yuboring 📸\n\n"
        "✨ <b>Yoki boshqa kanaldagi postni to'g'ridan-to'g'ri bu yerga forward qiling yoki post havolasini (link) yuboring!</b>\n\n"
        "<i>Rasmlarni yuborib bo'lgach, 'Keyingisi ➡️' tugmasini bosing yoki /cancel bosing.</i>"
    )

    markup = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Keyingisi ➡️")],
            [KeyboardButton(text="❌ Bekor qilish")],
        ],
        resize_keyboard=True,
    )
    await callback.message.answer(msg, reply_markup=markup)
    await callback.answer()


@router.message(ProductWizard.photos, F.photo)
async def process_wizard_photo(message: Message, state: FSMContext):
    data = await state.get_data()
    photos = data.get("photos", [])
    photos.append(message.photo[-1].file_id)
    await state.update_data(photos=photos)

    await message.answer(f"📸 Rasm qo'shildi! Jami rasmlar: {len(photos)} ta.\n\nYana rasm yuborishingiz yoki 'Keyingisi ➡️' tugmasini bosishingiz mumkin.")


@router.message(ProductWizard.photos, F.text == "Keyingisi ➡️")
async def process_photos_done(message: Message, state: FSMContext):
    data = await state.get_data()
    photos = data.get("photos", [])
    if not photos:
        await message.answer("⚠️ Kamida 1 ta rasm yuborishingiz kerak!")
        return

    await state.set_state(ProductWizard.title)
    await message.answer(
        "🌸 <b>2/8 qadam:</b> Mahsulot nomini kiriting:\n(Masalan: <i>Aesthetic Vintage Pushti Jempir 🌸</i>)",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="⬅️ Orqaga")], [KeyboardButton(text="❌ Bekor qilish")]],
            resize_keyboard=True,
        ),
    )


@router.message(ProductWizard.title, F.text)
async def process_wizard_title(message: Message, state: FSMContext):
    if message.text == "⬅️ Orqaga":
        await state.set_state(ProductWizard.photos)
        await message.answer("Rasmlarni yuboring:")
        return

    title = message.text.strip()
    await state.update_data(title=title)
    await state.set_state(ProductWizard.price)
    await message.answer(
        f"💰 <b>3/8 qadam:</b> Narxini so'mda kiriting:\n(Masalan: <code>99000</code> yoki <code>99.000</code>)",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="⬅️ Orqaga")], [KeyboardButton(text="❌ Bekor qilish")]],
            resize_keyboard=True,
        ),
    )


@router.message(ProductWizard.price, F.text)
async def process_wizard_price(message: Message, state: FSMContext):
    if message.text == "⬅️ Orqaga":
        data = await state.get_data()
        if data.get("source_label"):
            await state.clear()
            await message.answer("Bekor qilindi.", reply_markup=ReplyKeyboardRemove())
            return
        await state.set_state(ProductWizard.title)
        await message.answer("Nomini kiriting:")
        return
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("Bekor qilindi.", reply_markup=ReplyKeyboardRemove())
        return

    raw_text = message.text.strip()
    parsed = parse_channel_post(raw_text, apply_margin=True)
    source_price = parsed["source_price"]
    retail_price = parsed["retail_price"]
    margin_percent = parsed["margin_percent"]

    if not retail_price:
        digits = re.sub(r"\D", "", raw_text)
        if digits and int(digits) > 0:
            val = int(digits)
            if "yuan" in raw_text.lower() or "¥" in raw_text or "rmb" in raw_text.lower():
                source_price = int(round(val * 1800))
                margin_percent = calculate_margin_percent(source_price)
                retail_price = calculate_retail_price(source_price, margin_percent)
            else:
                retail_price = val
                margin_percent = calculate_margin_percent(val)
                source_price = int(round(val / (1 + margin_percent / 100)))

    if not retail_price or retail_price <= 0:
        await message.answer("⚠️ Iltimos, to'g'ri narx kiriting (masalan: <code>35 yuan</code> yoki <code>95000</code>):")
        return

    await state.update_data(price=retail_price, source_price=source_price, margin_percent=margin_percent)
    data = await state.get_data()

    # If in import/screenshot flow:
    if data.get("source_label"):
        if not data.get("sizes"):
            await state.set_state(ProductWizard.sizes)
            await message.answer(
                "🐾 <b>2-qadam: Mahsulot razmerlarini kiriting:</b>\n(Masalan: <code>S-2XL</code> yoki <code>S, M, L</code> yoki 'Standart' tugmasini bosing):",
                reply_markup=ReplyKeyboardMarkup(
                    keyboard=[
                        [KeyboardButton(text="Standart 🌸")],
                        [KeyboardButton(text="S, M, L"), KeyboardButton(text="S-2XL")],
                        [KeyboardButton(text="❌ Bekor qilish")],
                    ],
                    resize_keyboard=True,
                ),
            )
            return

        if not data.get("colors"):
            await state.set_state(ProductWizard.colors)
            await message.answer(
                "🎨 <b>3-qadam: Mahsulot ranglarini kiriting:</b>\n(Masalan: <code>Oq, Qora, Pushti</code> yoki 'Rasmda ko'rsatilgan' tugmasini bosing):",
                reply_markup=ReplyKeyboardMarkup(
                    keyboard=[
                        [KeyboardButton(text="Rasmda ko'rsatilgan (Standart) 🌸")],
                        [KeyboardButton(text="Oq, Qora"), KeyboardButton(text="Oq, Qora, Pushti")],
                        [KeyboardButton(text="❌ Bekor qilish")],
                    ],
                    resize_keyboard=True,
                ),
            )
            return

        await show_product_import_summary(message, state)
        return

    # Standard manual wizard flow:
    async with async_session_factory() as session:
        res = await session.execute(select(Category).order_by(Category.sort_order))
        categories = res.scalars().all()

    buttons = []
    row = []
    for c in categories:
        row.append(InlineKeyboardButton(text=f"#{c.slug} {c.emoji}", callback_data=f"cat_pick_{c.slug}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    await state.set_state(ProductWizard.category)
    await message.answer(
        f"🏷️ <b>4/8 qadam:</b> Kategoriyani tanlang:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
    )


@router.callback_query(ProductWizard.category, F.data.startswith("cat_pick_"))
async def process_wizard_category(callback: CallbackQuery, state: FSMContext):
    slug = callback.data.replace("cat_pick_", "")
    await state.update_data(category=slug)

    await state.set_state(ProductWizard.sizes)
    await callback.message.answer(
        "📏 <b>5/8 qadam:</b> O'lchamlarni kiriting (vergul bilan ajratib, masalan: <i>S, M, L</i>) yoki o'tkazib yuboring:",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="O'tkazib yuborish ⏭️")],
                [KeyboardButton(text="⬅️ Orqaga"), KeyboardButton(text="❌ Bekor qilish")],
            ],
            resize_keyboard=True,
        ),
    )
    await callback.answer()


@router.message(ProductWizard.sizes, F.text)
async def process_wizard_sizes(message: Message, state: FSMContext):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("Bekor qilindi.", reply_markup=ReplyKeyboardRemove())
        return

    text = message.text.strip()
    if "standart" in text.lower() or text in ["O'tkazib yuborish ⏭️", "Standart 🌸"]:
        sizes = ["Standart"]
    else:
        from api.services.formatters import parse_sizes
        sizes = parse_sizes(text)
        if not sizes:
            sizes = [s.strip() for s in text.split(",") if s.strip()]

    await state.update_data(sizes=sizes)
    data = await state.get_data()

    # Check if in import/screenshot flow:
    if data.get("source_label"):
        if not data.get("colors"):
            await state.set_state(ProductWizard.colors)
            await message.answer(
                "🎨 <b>3-qadam: Ranglarni kiriting:</b>\n(Masalan: <code>Oq, Qora, Pushti</code> yoki 'Rasmda ko'rsatilgan' tugmasini bosing):",
                reply_markup=ReplyKeyboardMarkup(
                    keyboard=[
                        [KeyboardButton(text="Rasmda ko'rsatilgan (Standart) 🌸")],
                        [KeyboardButton(text="Oq, Qora"), KeyboardButton(text="Oq, Qora, Pushti")],
                        [KeyboardButton(text="❌ Bekor qilish")],
                    ],
                    resize_keyboard=True,
                ),
            )
            return

        await show_product_import_summary(message, state)
        return

    # Normal wizard flow:
    await state.set_state(ProductWizard.colors)
    await message.answer(
        "🎨 <b>6/8 qadam:</b> Ranglarni kiriting (vergul bilan ajratib, masalan: <i>Pushti 🌸, Oq 🤍</i>) yoki o'tkazib yuboring:",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="O'tkazib yuborish ⏭️")],
                [KeyboardButton(text="⬅️ Orqaga"), KeyboardButton(text="❌ Bekor qilish")],
            ],
            resize_keyboard=True,
        ),
    )


@router.message(ProductWizard.colors, F.text)
async def process_wizard_colors(message: Message, state: FSMContext):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("Bekor qilindi.", reply_markup=ReplyKeyboardRemove())
        return

    text = message.text.strip()
    if "standart" in text.lower() or "rasmda" in text.lower() or text in ["O'tkazib yuborish ⏭️", "Rasmda ko'rsatilgan (Standart) 🌸"]:
        colors = ["Rasmda ko'rsatilgan"]
    else:
        colors = [c.strip() for c in re.split(r"[,;/|]+", text) if c.strip()]

    await state.update_data(colors=colors)
    data = await state.get_data()

    # Check if in import/screenshot flow:
    if data.get("source_label"):
        await show_product_import_summary(message, state)
        return

    # Normal wizard flow continues to weight:
    await state.set_state(ProductWizard.weight)
    await message.answer(
        "⚖️ <b>7/8 qadam:</b> Mahsulot og'irligini grammda kiriting (kargoni hisoblash uchun, masalan: <i>350</i>) yoki o'tkazib yuboring:",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="O'tkazib yuborish ⏭️")],
                [KeyboardButton(text="⬅️ Orqaga"), KeyboardButton(text="❌ Bekor qilish")],
            ],
            resize_keyboard=True,
        ),
    )


@router.message(ProductWizard.weight, F.text)
async def process_wizard_weight(message: Message, state: FSMContext):
    weight_grams = None
    if message.text != "O'tkazib yuborish ⏭️" and message.text != "⬅️ Orqaga":
        raw = re.sub(r"\D", "", message.text)
        if raw:
            weight_grams = int(raw)

    await state.update_data(weight_grams=weight_grams)
    await state.set_state(ProductWizard.description)
    await message.answer(
        "📝 <b>8/8 qadam:</b> Tavsif/qo'shimcha ma'lumot kiriting yoki o'tkazib yuboring:",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="O'tkazib yuborish ⏭️")],
                [KeyboardButton(text="⬅️ Orqaga"), KeyboardButton(text="❌ Bekor qilish")],
            ],
            resize_keyboard=True,
        ),
    )


@router.message(ProductWizard.description, F.text)
async def process_wizard_description(message: Message, state: FSMContext):
    desc_val = ""
    if message.text != "O'tkazib yuborish ⏭️" and message.text != "⬅️ Orqaga":
        desc_val = message.text.strip()

    await state.update_data(description=desc_val)
    data = await state.get_data()

    # Build Preview
    cargo = calculate_cargo(data.get("weight_grams"))
    sizes_str = ", ".join(data.get("sizes", [])) or "Ko'rsatilmagan"
    colors_str = ", ".join(data.get("colors", [])) or "Ko'rsatilmagan"

    preview = (
        "🌸 <b>MAHSULOT PREVIEW (Ko'rinishi):</b>\n\n"
        f"🏷️ <b>Kategoriya:</b> #{data['category']}\n"
        f"🎀 <b>Nomi:</b> {escape(data['title'])}\n"
        f"💰 <b>Narxi:</b> {format_price(data['price'])}\n"
        "📦 <b>Kargo tariflari (har 100g uchun alohida):</b>\n"
        "  ✈️ <b>AVIA:</b> 14.000 so'm / 100g (7–9 kun)\n"
        "  🚗 <b>AVTO:</b> 10.000 so'm / 100g (14–18 kun)\n"
        f"📏 <b>O'lchamlar:</b> {escape(sizes_str)}\n"
        f"🎨 <b>Ranglar:</b> {escape(colors_str)}\n"
        f"📝 <b>Tavsif:</b> {escape(data['description'] or 'Mavjud emas')}\n"
        f"📸 <b>Rasmlar:</b> {len(data['photos'])} ta"
    )

    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Saqlash & Kanalga joylash",
                    callback_data="wizard_save",
                    icon_custom_emoji_id=PREMIUM_BTN_BAG_ID,
                    style="primary",
                ),
                InlineKeyboardButton(text="✏️ Qayta kiritish", callback_data="admin_add_product"),
            ],
            [
                InlineKeyboardButton(text="❌ Bekor qilish", callback_data="admin_cancel"),
            ]
        ]
    )

    await state.set_state(ProductWizard.confirm)
    await message.answer(upgrade_to_premium_emojis(preview), reply_markup=markup)


@router.callback_query(F.data.in_(["wizard_save", "wizard_save_fast"]))
async def handle_save_product(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    if not data or not data.get("title") or not data.get("price"):
        await callback.answer("Ma'lumotlar topilmadi, qaytadan urinib ko'ring.", show_alert=True)
        return

    category_slug = (data.get("category") or "jempir").lower().replace("#", "").strip()

    async with async_session_factory() as session:
        # 1. Ensure category exists or auto-create it
        cat_res = await session.execute(select(Category).where(Category.slug == category_slug))
        if not cat_res.scalars().first():
            slug_emojis = {
                "hoodie": "🧥", "hudi": "🧥", "jempir": "🧶", "sviter": "🧶",
                "wig": "💇‍♀️", "parik": "💇‍♀️", "scarf": "🧣", "sharf": "🧣",
                "sumka": "👜", "koylak": "👗", "yubka": "👗", "skirt": "👗",
                "oyoqkiyim": "👠", "shoes": "👟", "krossovka": "👟", "aksessuar": "🎀",
                "kosmetika": "💄", "tuxedo": "🤵", "shim": "👖", "pants": "👖",
            }
            emoji = slug_emojis.get(category_slug, "🌸")
            max_order_res = await session.execute(select(func.coalesce(func.max(Category.sort_order), 0)))
            max_order = max_order_res.scalar() or 0
            session.add(Category(
                slug=category_slug,
                name=category_slug.capitalize(),
                emoji=emoji,
                sort_order=max_order + 1,
            ))
            await session.commit()

        # 2. Save product with source_price and retail price
        prod = Product(
            title=data["title"],
            description=data.get("description", ""),
            price=data["price"],
            old_price=data.get("old_price"),
            source_price=data.get("source_price"),
            category=category_slug,
            photos=data.get("photos", []),
            sizes=data.get("sizes", []),
            colors=data.get("colors", []),
            weight_grams=data.get("weight_grams"),
            in_stock=True,
            is_new=True,
        )
        session.add(prod)
        await session.commit()
        await session.refresh(prod)
        prod_id = prod.id

    await state.clear()
    await callback.answer("Saqlandi!")

    # 3. Auto-publish to Moonlight channel adapted to brand
    channel_res = await post_product_to_channel(prod)
    if channel_res.get("success"):
        sizes_txt = format_sizes_display(prod.sizes) if prod.sizes else "Standart"
        saved_msg = (
            f"✅ <b>Mahsulot muvaffaqiyatli saqlandi va kanalga joylandi! (#{prod_id})</b> 🌸\n\n"
            f"🏷️ <b>Kategoriya:</b> #{prod.category}\n"
            f"🎀 <b>Nomi:</b> {escape(prod.title)}\n"
            f"💰 <b>Sotuv narxi:</b> {format_price(prod.price)}\n"
            f"📥 <b>Asl narxi:</b> {format_price(prod.source_price) if prod.source_price else '—'}\n"
            f"📦 <b>Kargo tariflari (har 100g alohida):</b>\n"
            f"  ✈️ AVIA: 14.000 so'm / 100g (7–9 kun)\n"
            f"  🚗 AVTO: 10.000 so'm / 100g (14–18 kun)\n"
            f"👗 <b>O'lchamlar:</b> {escape(sizes_txt)}\n"
            f"📢 <b>Kanal:</b> @moonlight_chinese_shop\n"
            f"🛍️ Mini App havolasi ulandi."
        )
        await callback.message.edit_text(
            upgrade_to_premium_emojis(saved_msg),
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="➕ Yana mahsulot",
                            callback_data="admin_add_product",
                            icon_custom_emoji_id=PREMIUM_BTN_BAG_ID,
                            style="primary",
                        ),
                        InlineKeyboardButton(text="👑 Bosh menyu", callback_data="admin_done"),
                    ]
                ]
            )
        )
    else:
        err_msg = channel_res.get("error", "Noma'lum xatolik")
        await callback.message.edit_text(
            f"✅ <b>Mahsulot do'konda saqlandi! (#{prod_id})</b> 🌸\n\n"
            f"⚠️ <b>Kanalga avtomatik joylashda xatolik:</b>\n{escape(str(err_msg))}\n\n"
            f"Bot kanalingizda administrator ekanligini tekshirib, qayta kanalga joylashingiz mumkin:",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="📢 Qayta kanalga joylash",
                            callback_data=f"post_channel_now_{prod_id}",
                        ),
                        InlineKeyboardButton(
                            text="👑 Bosh menyu",
                            callback_data="admin_done",
                        )
                    ]
                ]
            )
        )


@router.callback_query(F.data.startswith("post_channel_now_"))
async def handle_post_channel_now(callback: CallbackQuery):
    prod_id = int(callback.data.replace("post_channel_now_", ""))
    async with async_session_factory() as session:
        res = await session.execute(select(Product).where(Product.id == prod_id))
        prod = res.scalars().first()
        if not prod:
            await callback.answer("Mahsulot topilmadi", show_alert=True)
            return

        result = await post_product_to_channel(prod)

    if result.get("success"):
        await callback.message.edit_text(
            f"✅ <b>Mahsulot kanalga muvaffaqiyatli joylandi!</b> 🌸\n"
            f"Do'konda ko'rish havolasi bilan birga post qilindi."
        )
    else:
        await callback.message.edit_text(
            f"⚠️ <b>Kanalga joylashda xatolik:</b>\n{result.get('error')}\n\n"
            f"Bot kanalingizda administrator ekanligini va ruxsatlari borligini tekshiring."
        )
    await callback.answer()


# ==================== PRODUCT LIST & MANAGEMENT ====================
@router.callback_query(F.data == "admin_list_products")
async def handle_list_products(callback: CallbackQuery):
    async with async_session_factory() as session:
        res = await session.execute(select(Product).order_by(desc(Product.created_at)).limit(10))
        products = res.scalars().all()

    if not products:
        await callback.message.edit_text(
            "🌸 Hozircha birorta ham mahsulot yo'q.",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text="➕ Qo'shish", callback_data="admin_add_product")]]
            )
        )
        await callback.answer()
        return

    buttons = []
    for p in products:
        stock_emoji = "✅" if p.in_stock else "❌"
        buttons.append([
            InlineKeyboardButton(
                text=f"{stock_emoji} {p.title[:25]} ({format_price(p.price)})",
                callback_data=f"admin_prod_manage_{p.id}",
            )
        ])
    buttons.append([InlineKeyboardButton(text="⬅️ Orqaga", callback_data="admin_menu")])

    await callback.message.edit_text(
        "📦 <b>Mahsulotlar ro'yxati:</b>\nBoshqarish yoki o'zgartirish uchun mahsulotni tanlang:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_prod_manage_"))
async def handle_manage_single_product(callback: CallbackQuery):
    prod_id = int(callback.data.replace("admin_prod_manage_", ""))
    async with async_session_factory() as session:
        res = await session.execute(select(Product).where(Product.id == prod_id))
        p = res.scalars().first()

    if not p:
        await callback.answer("Mahsulot topilmadi", show_alert=True)
        return

    stock_text = "Mavjud (In stock) ✅" if p.in_stock else "Sotildi ❌"
    hit_str = "Ha" if p.is_hit else "Yo'q"
    new_str = "Ha" if p.is_new else "Yo'q"
    text = (
        f"🌸 <b>{escape(str(p.title))}</b>\n"
        f"🏷️ Kategoriya: #{p.category}\n"
        f"💰 Narxi: {format_price(p.price)}\n"
        f"📊 Holati: <b>{stock_text}</b>\n"
        f"👁️ Ko'rishlar: {p.views}\n"
        f"🔥 Hit: {hit_str} | 🆕 Yangi: {new_str}"
    )

    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Holatni almashtirish 🔄 (Sotildi/Mavjud)",
                    callback_data=f"admin_toggle_stock_{p.id}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="📢 Kanalga joylash",
                    callback_data=f"post_channel_now_{p.id}"
                ),
                InlineKeyboardButton(
                    text="🔥 Hit / 🆕 Yangi",
                    callback_data=f"admin_toggle_badges_{p.id}"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🗑️ O'chirish",
                    callback_data=f"admin_confirm_delete_prod_{p.id}"
                ),
                InlineKeyboardButton(text="⬅️ Ro'yxatga", callback_data="admin_list_products"),
            ]
        ]
    )

    await callback.message.edit_text(text, reply_markup=markup)
    await callback.answer()


@router.callback_query(F.data.startswith("admin_toggle_stock_"))
async def handle_toggle_stock(callback: CallbackQuery):
    prod_id = int(callback.data.replace("admin_toggle_stock_", ""))
    async with async_session_factory() as session:
        res = await session.execute(select(Product).where(Product.id == prod_id))
        p = res.scalars().first()
        if p:
            p.in_stock = not p.in_stock
            await session.commit()
    await handle_manage_single_product(callback)


@router.callback_query(F.data.startswith("admin_confirm_delete_prod_"))
async def handle_confirm_delete_prod(callback: CallbackQuery):
    prod_id = int(callback.data.replace("admin_confirm_delete_prod_", ""))
    async with async_session_factory() as session:
        res = await session.execute(select(Product).where(Product.id == prod_id))
        p = res.scalars().first()
        if p:
            await session.delete(p)
            await session.commit()

    await callback.answer("🗑️ Mahsulot o'chirildi", show_alert=True)
    await handle_list_products(callback)


# ==================== STATS ====================
@router.callback_query(F.data == "admin_stats")
async def handle_admin_stats(callback: CallbackQuery):
    async with async_session_factory() as session:
        total_users = (await session.execute(select(func.count(User.telegram_id)))).scalar() or 0
        total_orders = (await session.execute(select(func.count(Order.id)))).scalar() or 0
        new_orders = (await session.execute(select(func.count(Order.id)).where(Order.status == "new"))).scalar() or 0
        total_prods = (await session.execute(select(func.count(Product.id)))).scalar() or 0
        in_stock_prods = (await session.execute(select(func.count(Product.id)).where(Product.in_stock == True))).scalar() or 0

    text = (
        "📊 <b>Moonlight Chinese Shop — Statistika:</b> 🌸\n\n"
        f"👥 <b>Foydalanuvchilar:</b> {total_users} ta\n"
        f"🧾 <b>Jami buyurtmalar:</b> {total_orders} ta\n"
        f"⏳ <b>Yangi (kutilayotgan) buyurtmalar:</b> {new_orders} ta\n"
        f"📦 <b>Jami mahsulotlar:</b> {total_prods} ta\n"
        f"✅ <b>Sotuvda mavjud:</b> {in_stock_prods} ta\n\n"
        "Batafsil grafiklar va monitoring Mini App 👑 Admin bo'limida mavjud!"
    )

    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="👑 Mini App'da to'liq statistika", web_app=WebAppInfo(url=f"{settings.WEBAPP_URL}?tab=admin"))],
            [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="admin_menu")]
        ]
    )
    await callback.message.edit_text(text, reply_markup=markup)
    await callback.answer()


# ==================== SETTINGS & ADMIN MANAGEMENT ====================
@router.callback_query(F.data == "admin_settings")
async def handle_admin_settings_menu(callback: CallbackQuery):
    user_id = callback.from_user.id
    async with async_session_factory() as session:
        res = await session.execute(select(Admin))
        admins = res.scalars().all()
        res_ch = await session.execute(select(Setting).where(Setting.key == "channel_id"))
        ch = res_ch.scalars().first()
        channel_status = f"Uланган ({ch.value}) ✅" if (ch and ch.value) else "Ulanmagan ❌"

    admin_lines = []
    for a in admins:
        role_badge = "👑 Egasi (Owner)" if a.role == "owner" else "Admin"
        admin_lines.append(f"• {escape(str(a.name))} (<code>{a.telegram_id}</code>) — {role_badge}")

    text = (
        "⚙️ <b>Do'kon sozlamalari:</b> 🌸\n\n"
        f"📢 <b>Kanal:</b> {channel_status}\n\n"
        f"👥 <b>Adminlar ro'yxati:</b>\n" + "\n".join(admin_lines) + "\n\n"
        "Yangi admin qo'shish yoki sozlamalarni o'zgartirish:"
    )

    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="👑 Yangi Owner qo'shish", callback_data="admin_add_co_owner"),
                InlineKeyboardButton(text="➕ Yangi Admin qo'shish", callback_data="admin_add_new_admin"),
            ],
            [
                InlineKeyboardButton(text="🔗 Kanalni ulash", callback_data="admin_link_channel"),
                InlineKeyboardButton(text="📢 Kanalni uzish", callback_data="admin_unlink_channel"),
            ],
            [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="admin_menu")],
        ]
    )
    await callback.message.edit_text(text, reply_markup=markup)
    await callback.answer()


@router.callback_query(F.data == "admin_add_co_owner")
async def handle_start_add_co_owner(callback: CallbackQuery, state: FSMContext):
    async with async_session_factory() as session:
        caller = (
            await session.execute(select(Admin).where(Admin.telegram_id == callback.from_user.id))
        ).scalars().first()
        # Plain admins must not be able to promote themselves or others to owner.
        if not (caller and caller.role == "owner") and callback.from_user.id != settings.DEV_ADMIN_ID:
            await callback.answer("⛔ Yangi egani faqat do'kon egasi qo'sha oladi.", show_alert=True)
            return
        token = await create_owner_invite(session)
    await state.set_state(AdminSettingsState.waiting_for_owner_forward)
    bot_me = await callback.bot.get_me()
    invite_link = f"https://t.me/{bot_me.username}?start=claim_{token}"
    await callback.message.answer(
        "👑 <b>Yangi Do'kon Egasi (Co-Owner) qo'shish:</b>\n\n"
        "2 xil usulda qo'shishingiz mumkin:\n\n"
        "1️⃣ <b>Havola orqali:</b> Quyidagi havolani o'sha insonga yuboring, u bitta bosishda teng huquqli Owner bo'ladi.\n"
        "⚠️ Havola <b>faqat bir marta</b> ishlaydi va uni faqat o'sha insonga yuboring. Yangi havola yaratilsa, eskisi o'chadi.\n"
        f"👉 <code>{invite_link}</code>\n\n"
        "2️⃣ <b>Yoki shu yerda:</b> O'sha insonning istalgan xabarini bu yerga <b>forward</b> qiling, kontaktini yuboring yoki uning Telegram ID raqamini yozing:",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="❌ Bekor qilish")]],
            resize_keyboard=True,
        )
    )
    await callback.answer()


@router.message(AdminSettingsState.waiting_for_owner_forward)
async def process_new_owner_forward(message: Message, state: FSMContext):
    text_val = (message.text or "").strip()
    if text_val in ["❌ Bekor qilish", "/cancel"]:
        await state.clear()
        await message.answer("❌ Jarayon bekor qilindi.", reply_markup=get_main_reply_keyboard())
        await message.answer("👑 Admin menyusi:", reply_markup=get_admin_main_keyboard())
        return

    new_owner_id = None
    new_owner_name = ""
    new_owner_username = None

    if message.forward_from:
        new_owner_id = message.forward_from.id
        new_owner_name = message.forward_from.full_name or "Co-Owner"
        new_owner_username = message.forward_from.username
    elif message.contact:
        new_owner_id = message.contact.user_id
        new_owner_name = message.contact.first_name or "Co-Owner"
    elif text_val.isdigit():
        new_owner_id = int(text_val)
        new_owner_name = "Co-Owner"
    elif text_val.startswith("@") or re.match(r'^[a-zA-Z0-9_]{4,}$', text_val):
        clean_user = text_val.lstrip("@").lower()
        async with async_session_factory() as session:
            res_u = await session.execute(select(User).where(func.lower(User.username) == clean_user))
            u = res_u.scalars().first()
            if u:
                new_owner_id = u.telegram_id
                new_owner_name = u.name or clean_user
                new_owner_username = u.username

    # Handle forward from user whose Telegram privacy hides account ID
    if not new_owner_id and message.forward_sender_name:
        clean_sender = message.forward_sender_name.strip().lower()
        async with async_session_factory() as session:
            res_u = await session.execute(select(User).where(func.lower(User.name) == clean_sender))
            u = res_u.scalars().first()
            if u:
                new_owner_id = u.telegram_id
                new_owner_name = u.name
                new_owner_username = u.username

    if not new_owner_id:
        bot_info = await message.bot.get_me() if message.bot else None
        b_user = bot_info.username if bot_info and bot_info.username else "moonlight_chinese_bot"
        invite_link = f"https://t.me/{b_user}?start=claim_{settings.OWNER_SETUP_CODE}"
        await message.answer(
            "⚠️ <b>Foydalanuvchini aniqlab bo'lmadi!</b>\n\n"
            "Telegram maxfiylik sozlamalari (Forward Privacy) bu insonning profilini yashirgan bo'lishi mumkin.\n\n"
            "Uni Owner qilishning eng oson yo'llari:\n"
            f"1️⃣ O'sha insonga mana bu havolani yuboring (u 1 ta bosishda Owner bo'ladi):\n<code>{invite_link}</code>\n\n"
            "2️⃣ Yoki uning <b>@username</b> yoki <b>Telegram ID</b> raqamini yozing:"
        )
        return

    async with async_session_factory() as session:
        res = await session.execute(select(Admin).where(Admin.telegram_id == new_owner_id))
        existing = res.scalars().first()
        if existing:
            existing.role = "owner"
            await session.commit()
            await message.answer(f"✅ <b>{existing.name}</b> (ID: <code>{new_owner_id}</code>) ning roli <b>Owner</b> ga yangilandi! 👑")
        else:
            session.add(Admin(telegram_id=new_owner_id, name=new_owner_name, username=new_owner_username, role="owner"))
            await session.commit()
            await message.answer(f"✅ <b>{new_owner_name}</b> (ID: <code>{new_owner_id}</code>) muvaffaqiyatli teng huquqli <b>Do'kon Egasi (Owner)</b> etib tayinlandi! 👑🌸")

    await state.clear()
    await message.answer("👑 Admin menyusi:", reply_markup=get_admin_main_keyboard())


@router.callback_query(F.data == "admin_add_new_admin")
async def handle_start_add_admin(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AdminSettingsState.waiting_for_admin_forward)
    await callback.message.answer(
        "👤 <b>Yangi admin qo'shish:</b>\n\n"
        "Iltimos, o'sha odamning istalgan xabarini bu yerga <b>forward</b> qiling, yoki uning kontaktini yuboring:",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="❌ Bekor qilish")]],
            resize_keyboard=True,
        )
    )
    await callback.answer()


@router.message(AdminSettingsState.waiting_for_admin_forward)
async def process_new_admin_forward(message: Message, state: FSMContext):
    text_val = (message.text or "").strip()
    if text_val in ["❌ Bekor qilish", "/cancel"]:
        await state.clear()
        await message.answer("❌ Jarayon bekor qilindi.", reply_markup=get_main_reply_keyboard())
        await message.answer("👑 Admin menyusi:", reply_markup=get_admin_main_keyboard())
        return

    new_admin_id = None
    new_admin_name = ""
    new_admin_username = None

    if message.forward_from:
        new_admin_id = message.forward_from.id
        new_admin_name = message.forward_from.full_name or "Admin"
        new_admin_username = message.forward_from.username
    elif message.contact:
        new_admin_id = message.contact.user_id
        new_admin_name = message.contact.first_name or "Admin"
    elif text_val.isdigit():
        new_admin_id = int(text_val)
        new_admin_name = "Admin"
    elif text_val.startswith("@") or re.match(r'^[a-zA-Z0-9_]{4,}$', text_val):
        clean_user = text_val.lstrip("@").lower()
        async with async_session_factory() as session:
            res_u = await session.execute(select(User).where(func.lower(User.username) == clean_user))
            u = res_u.scalars().first()
            if u:
                new_admin_id = u.telegram_id
                new_admin_name = u.name or clean_user
                new_admin_username = u.username

    # Handle forward from user whose Telegram privacy hides account ID
    if not new_admin_id and message.forward_sender_name:
        clean_sender = message.forward_sender_name.strip().lower()
        async with async_session_factory() as session:
            res_u = await session.execute(select(User).where(func.lower(User.name) == clean_sender))
            u = res_u.scalars().first()
            if u:
                new_admin_id = u.telegram_id
                new_admin_name = u.name
                new_admin_username = u.username

    if not new_admin_id:
        await message.answer(
            "⚠️ <b>Foydalanuvchini aniqlab bo'lmadi!</b>\n\n"
            "Telegram maxfiylik sozlamalari (Forward Privacy) bu insonning profilini yashirgan bo'lishi mumkin.\n\n"
            "Iltimos, uning <b>@username</b> yoki <b>Telegram ID</b> raqamini yozing:"
        )
        return

    async with async_session_factory() as session:
        existing = await session.execute(select(Admin).where(Admin.telegram_id == new_admin_id))
        if existing.scalars().first():
            await message.answer("Ushbu foydalanuvchi allaqachon admin yoki owner!")
        else:
            session.add(Admin(telegram_id=new_admin_id, name=new_admin_name, username=new_owner_username if 'new_owner_username' in locals() else new_admin_username, role="admin"))
            await session.commit()
            await message.answer(f"✅ <b>{new_admin_name}</b> (ID: <code>{new_admin_id}</code>) muvaffaqiyatli admin etib tayinlandi! 🌸")

    await state.clear()
    await message.answer("👑 Admin menyusi:", reply_markup=get_admin_main_keyboard())


# ==================== CATEGORIES MANAGEMENT ====================
@router.callback_query(F.data == "admin_categories")
async def handle_admin_categories_list(callback: CallbackQuery, state: FSMContext = None):
    if state:
        await state.clear()
    async with async_session_factory() as session:
        res = await session.execute(select(Category).order_by(Category.sort_order))
        categories = res.scalars().all()

        cat_counts = {}
        for c in categories:
            prod_c = await session.execute(select(func.count(Product.id)).where(Product.category == c.slug))
            cat_counts[c.slug] = prod_c.scalar() or 0

    buttons = []
    for c in categories:
        count = cat_counts.get(c.slug, 0)
        buttons.append([
            InlineKeyboardButton(
                text=f"{c.emoji} #{c.name} ({count} ta)",
                callback_data=f"admin_manage_cat_{c.slug}",
            )
        ])

    buttons.append([InlineKeyboardButton(text="➕ Yangi bo'lim qo'shish", callback_data="admin_add_cat")])
    buttons.append([InlineKeyboardButton(text="⬅️ Orqaga", callback_data="admin_menu")])

    text = (
        "🗂 <b>Do'kon bo'limlari (kategoriyalar):</b> 🌸\n\n"
        "O'chirish yoki ma'lumotlarini ko'rish uchun bo'lim ustiga bosing, yoki yangi bo'lim qo'shing:"
    )
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
    await callback.answer()


@router.callback_query(F.data.startswith("admin_manage_cat_"))
async def handle_manage_single_category(callback: CallbackQuery):
    slug = callback.data.replace("admin_manage_cat_", "").strip()
    async with async_session_factory() as session:
        res = await session.execute(select(Category).where(Category.slug == slug))
        cat = res.scalars().first()
        prod_c = await session.execute(select(func.count(Product.id)).where(Product.category == slug))
        count = prod_c.scalar() or 0

    if not cat:
        await callback.answer("Bo'lim topilmadi", show_alert=True)
        return

    text = (
        f"🗂 <b>Bo'lim tafsilotlari:</b>\n\n"
        f"🏷 Nomi: <b>{escape(cat.name)}</b>\n"
        f"🌸 Belgisi: {cat.emoji}\n"
        f"🔑 Slug: <code>#{cat.slug}</code>\n"
        f"📦 Mahsulotlar soni: <b>{count} ta</b>\n\n"
        f"Ushbu bo'limni o'chirishni xohlaysizmi?"
    )

    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🗑️ Bo'limni o'chirish",
                    callback_data=f"admin_del_cat_{cat.slug}",
                )
            ],
            [InlineKeyboardButton(text="⬅️ Bo'limlar ro'yxatiga", callback_data="admin_categories")],
        ]
    )
    await callback.message.edit_text(text, reply_markup=markup)
    await callback.answer()


@router.callback_query(F.data.startswith("admin_del_cat_"))
async def handle_delete_category(callback: CallbackQuery):
    slug = callback.data.replace("admin_del_cat_", "").strip()
    async with async_session_factory() as session:
        res = await session.execute(select(Category).where(Category.slug == slug))
        cat = res.scalars().first()
        if cat:
            await session.execute(delete(Product).where(Product.category == slug))
            await session.delete(cat)
            await session.commit()

    await callback.answer("🗑️ Bo'lim va undagi mahsulotlar o'chirildi!", show_alert=True)
    await handle_admin_categories_list(callback, None)


@router.callback_query(F.data == "admin_add_cat")
async def handle_start_add_category(callback: CallbackQuery, state: FSMContext):
    await state.set_state(CategoryWizard.waiting_for_name)
    await callback.message.answer(
        "➕ <b>Yangi bo'lim qo'shish:</b>\n\n"
        "Yangi bo'lim nomini yozing (masalan: <i>Sumkalar</i>, <i>Koylaklar</i> yoki <i>Aksessuarlar</i>):",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="❌ Bekor qilish")]],
            resize_keyboard=True,
        )
    )
    await callback.answer()


@router.message(CategoryWizard.waiting_for_name)
async def process_cat_name(message: Message, state: FSMContext):
    name = (message.text or "").strip()
    if not name or name == "❌ Bekor qilish":
        await state.clear()
        await message.answer("❌ Bekor qilindi.", reply_markup=get_main_reply_keyboard())
        await message.answer("👑 Admin menyusi:", reply_markup=get_admin_main_keyboard())
        return

    clean_slug = re.sub(r'[^a-zA-Z0-9а-яА-ЯёЁ_]', '-', name.lower()).strip('-')
    await state.update_data(cat_name=name, cat_slug=clean_slug)
    await state.set_state(CategoryWizard.waiting_for_emoji)
    await message.answer(
        f"🌸 Bo'lim nomi: <b>{escape(name)}</b>\n\n"
        "Endi ushbu bo'lim uchun bitta mos <b>emoji</b> yuboring (masalan: 👜, 👗, 💍, 🎀 yoki 🌸):"
    )


@router.message(CategoryWizard.waiting_for_emoji)
async def process_cat_emoji(message: Message, state: FSMContext):
    emoji_char = (message.text or "").strip()
    if not emoji_char or emoji_char == "❌ Bekor qilish":
        await state.clear()
        await message.answer("❌ Bekor qilindi.", reply_markup=get_main_reply_keyboard())
        await message.answer("👑 Admin menyusi:", reply_markup=get_admin_main_keyboard())
        return

    data = await state.get_data()
    name = data.get("cat_name", "Kategoriya")
    slug = data.get("cat_slug", "kategoriya")

    async with async_session_factory() as session:
        existing = await session.execute(select(Category).where(Category.slug == slug))
        if existing.scalars().first():
            slug = f"{slug}-{int(datetime.now().timestamp()) % 1000}"

        new_cat = Category(
            slug=slug,
            name=name,
            emoji=emoji_char[:4],
            sort_order=10,
        )
        session.add(new_cat)
        await session.commit()

    await state.clear()
    await message.answer(
        f"✅ <b>{emoji_char} {escape(name)}</b> bo'limi muvaffaqiyatli qo'shildi! 🌸",
        reply_markup=get_main_reply_keyboard(),
    )
    await message.answer("👑 Admin menyusi:", reply_markup=get_admin_main_keyboard())


# ==================== REVIEWS MANAGEMENT ====================
@router.callback_query(F.data == "admin_reviews")
async def handle_admin_reviews_list(callback: CallbackQuery):
    async with async_session_factory() as session:
        res = await session.execute(select(Review).order_by(desc(Review.created_at)).limit(10))
        reviews = res.scalars().all()

    if not reviews:
        await callback.message.edit_text(
            "⭐ <b>Mijozlar fikrlari:</b>\n\nHozircha birorta ham fikr yo'q.",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text="⬅️ Orqaga", callback_data="admin_menu")]]
            )
        )
        await callback.answer()
        return

    buttons = []
    for r in reviews:
        status_icon = "✅" if r.approved else "⏳"
        author = r.customer_name or "Mijoz"
        text_snippet = (r.text or "")[:20]
        buttons.append([
            InlineKeyboardButton(
                text=f"{status_icon} {author}: \"{text_snippet}...\"",
                callback_data=f"admin_manage_review_{r.id}",
            )
        ])
    buttons.append([InlineKeyboardButton(text="⬅️ Orqaga", callback_data="admin_menu")])

    await callback.message.edit_text(
        "⭐ <b>Mijozlar fikrlari (oxirgi 10 ta):</b>\nO'chirish yoki tasdiqlash uchun fikrni tanlang:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_manage_review_"))
async def handle_manage_single_review(callback: CallbackQuery):
    rev_id = int(callback.data.replace("admin_manage_review_", ""))
    async with async_session_factory() as session:
        res = await session.execute(select(Review).where(Review.id == rev_id))
        r = res.scalars().first()

    if not r:
        await callback.answer("Fikr topilmadi", show_alert=True)
        return

    status_str = "Tasdiqlangan (Ko'rinmoqda) ✅" if r.approved else "Kutilmoqda ⏳"
    text = (
        f"⭐ <b>Mijoz fikri:</b>\n\n"
        f"👤 Muallif: <b>{escape(str(r.customer_name or 'Mijoz'))}</b>\n"
        f"📊 Holati: <b>{status_str}</b>\n\n"
        f"💬 Matn:\n<i>\"{escape(str(r.text or ''))}\"</i>"
    )

    toggle_btn_text = "🚫 Yashirish" if r.approved else "✅ Tasdiqlash (e'lon qilish)"
    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=toggle_btn_text,
                    callback_data=f"admin_toggle_rev_{r.id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🗑️ Fikrni o'chirish",
                    callback_data=f"admin_del_rev_{r.id}",
                )
            ],
            [InlineKeyboardButton(text="⬅️ Fikrlar ro'yxatiga", callback_data="admin_reviews")],
        ]
    )
    await callback.message.edit_text(text, reply_markup=markup)
    await callback.answer()


@router.callback_query(F.data.startswith("admin_toggle_rev_"))
async def handle_toggle_review_approval(callback: CallbackQuery):
    rev_id = int(callback.data.replace("admin_toggle_rev_", ""))
    async with async_session_factory() as session:
        res = await session.execute(select(Review).where(Review.id == rev_id))
        r = res.scalars().first()
        if r:
            r.approved = not r.approved
            await session.commit()

    await callback.answer("Holat yangilandi", show_alert=True)
    await handle_manage_single_review(callback)


@router.callback_query(F.data.startswith("admin_del_rev_"))
async def handle_delete_single_review(callback: CallbackQuery):
    rev_id = int(callback.data.replace("admin_del_rev_", ""))
    async with async_session_factory() as session:
        res = await session.execute(select(Review).where(Review.id == rev_id))
        r = res.scalars().first()
        if r:
            await session.delete(r)
            await session.commit()

    await callback.answer("🗑️ Fikr o'chirildi!", show_alert=True)
    await handle_admin_reviews_list(callback)


@router.callback_query(F.data.in_(["admin_menu", "admin_main_menu", "admin_done"]))
async def handle_return_admin_menu(callback: CallbackQuery, state: FSMContext = None):
    if state:
        await state.clear()
    try:
        await callback.message.edit_text("👑 <b>Moonlight Chinese Shop — Admin Paneli</b> 🌸", reply_markup=get_admin_main_keyboard())
    except Exception:
        await callback.message.answer("👑 <b>Moonlight Chinese Shop — Admin Paneli</b> 🌸", reply_markup=get_admin_main_keyboard())
    await callback.answer()


@router.callback_query(F.data == "admin_cancel")
async def handle_admin_cancel(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    try:
        await callback.message.edit_text("❌ Jarayon bekor qilindi.", reply_markup=get_admin_main_keyboard())
    except Exception:
        await callback.message.answer("❌ Jarayon bekor qilindi.", reply_markup=get_admin_main_keyboard())
    await callback.answer()


@router.callback_query(F.data == "admin_orders")
async def handle_admin_orders(callback: CallbackQuery):
    async with async_session_factory() as session:
        res = await session.execute(
            select(Order).order_by(Order.created_at.desc()).limit(8)
        )
        orders_list = res.scalars().all()

        pending_count = (await session.execute(
            select(func.count(Order.id)).where(Order.status.in_(["pending_approval", "awaiting_receipt", "new"]))
        )).scalar() or 0

    if not orders_list:
        text = (
            "🧾 <b>Buyurtmalar:</b> 🌸\n\n"
            "Hozircha do'konda buyurtmalar mavjud emas.\n\n"
            "Mijozlar buyurtma berganda bu yerda va Mini App'da ko'rinadi 💗"
        )
    else:
        status_map = {
            "awaiting_receipt": "Chek kutilmoqda ⏳",
            "pending_approval": "Tasdiqlash kutilmoqda 📩",
            "accepted": "Qabul qilingan ✅",
            "cancelled": "Bekor qilingan ❌",
            "new": "Yangi 🆕",
        }
        text_lines = [
            f"🧾 <b>Oxirgi buyurtmalar (Jami: {len(orders_list)} ta ko'rsatilmoqda):</b> 🌸\n"
            f"⏳ <i>Kutilayotgan: {pending_count} ta</i>\n"
        ]
        for o in orders_list:
            st = status_map.get(o.status, o.status)
            c_name = escape(str(o.customer_name or "Mijoz"))
            total_fmt = f"{o.total:,}".replace(",", ".")
            text_lines.append(f"• <b>#{o.id}</b> | {c_name} — {total_fmt} so'm ({st})")

        text_lines.append("\n💡 <i>Buyurtma holatini o'zgartirish va to'liq tafsilotlar uchun Mini App Admin paneliga kiring:</i>")
        text = "\n".join(text_lines)

    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="👑 Mini App'da boshqarish",
                    web_app=WebAppInfo(url=f"{settings.WEBAPP_URL}?tab=admin"),
                )
            ],
            [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="admin_menu")],
        ]
    )
    try:
        await callback.message.edit_text(text, reply_markup=markup)
    except Exception:
        await callback.message.answer(text, reply_markup=markup)
    await callback.answer()


@router.callback_query(F.data == "admin_broadcast")
async def handle_admin_broadcast_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AdminSettingsState.waiting_for_broadcast_text)
    cancel_kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="❌ Bekor qilish", callback_data="admin_cancel")]]
    )
    try:
        await callback.message.edit_text(
            "📣 <b>Barcha mijozlarga xabar yuborish (Broadcast):</b> 🌸\n\n"
            "Yubormoqchi bo'lgan xabaringizni yozing (matn, rasm yoki post ko'rinishida yuborishingiz mumkin).\n\n"
            "<i>Bekor qilish uchun '❌ Bekor qilish' tugmasini bosing yoki /cancel yuboring.</i>",
            reply_markup=cancel_kb,
        )
    except Exception:
        await callback.message.answer(
            "📣 <b>Barcha mijozlarga xabar yuborish (Broadcast):</b> 🌸\n\n"
            "Yubormoqchi bo'lgan xabaringizni yozing (matn, rasm yoki post ko'rinishida yuborishingiz mumkin).\n\n"
            "<i>Bekor qilish uchun '❌ Bekor qilish' tugmasini bosing yoki /cancel yuboring.</i>",
            reply_markup=cancel_kb,
        )
    await callback.answer()


@router.message(AdminSettingsState.waiting_for_broadcast_text)
async def process_broadcast_message(message: Message, state: FSMContext):
    if not await is_user_admin(message.from_user.id if message.from_user else 0):
        await state.clear()
        return

    await state.clear()

    async with async_session_factory() as session:
        res = await session.execute(select(User.telegram_id))
        user_ids = res.scalars().all()

    if not user_ids:
        await message.answer(
            "ℹ️ Foydalanuvchilar ro'yxati bo'sh.",
            reply_markup=get_admin_main_keyboard(),
        )
        return

    status_msg = await message.answer(f"⏳ Xabar yuborilmoqda... (Jami: {len(user_ids)} ta mijoz)")

    success = 0
    failed = 0

    from bot.loader import bot
    from aiogram.exceptions import TelegramRetryAfter
    if not bot:
        await status_msg.edit_text(
            "⚠️ Bot obyekti mavjud emas, xabar yuborilmadi.",
            reply_markup=get_admin_main_keyboard(),
        )
        return

    for uid in user_ids:
        sent = False
        for attempt in range(2):
            try:
                if message.photo:
                    try:
                        await bot.send_photo(
                            chat_id=uid,
                            photo=message.photo[-1].file_id,
                            caption=message.caption,
                            parse_mode="HTML",
                        )
                    except Exception:
                        await bot.send_photo(
                            chat_id=uid,
                            photo=message.photo[-1].file_id,
                            caption=message.caption,
                        )
                elif message.text:
                    try:
                        await bot.send_message(
                            chat_id=uid,
                            text=message.text,
                            parse_mode="HTML",
                        )
                    except Exception:
                        await bot.send_message(
                            chat_id=uid,
                            text=message.text,
                        )
                else:
                    await bot.copy_message(
                        chat_id=uid,
                        from_chat_id=message.chat.id,
                        message_id=message.message_id,
                    )
                success += 1
                sent = True
                await asyncio.sleep(0.04)
                break
            except TelegramRetryAfter as e:
                logger.warning(f"Rate limited by Telegram during broadcast, sleeping {e.retry_after}s...")
                await asyncio.sleep(e.retry_after + 0.5)
                continue
            except Exception as err:
                logger.warning(f"Broadcast failed for user {uid}: {err}")
                break
        if not sent:
            failed += 1

    summary_text = (
        "📣 <b>Broadcast natijasi:</b> 🌸\n\n"
        f"👥 Jami mijozlar: <b>{len(user_ids)}</b> ta\n"
        f"✅ Yetkazildi: <b>{success}</b> ta\n"
        f"⚠️ Yetkazilmadi (bloklangan/xatolik): <b>{failed}</b> ta"
    )
    try:
        await status_msg.edit_text(summary_text, reply_markup=get_admin_main_keyboard())
    except Exception:
        await message.answer(summary_text, reply_markup=get_admin_main_keyboard())


@router.callback_query(F.data == "admin_reset_confirm")
async def handle_admin_reset_confirm(callback: CallbackQuery):
    await callback.answer(
        "⛔ Ma'lumotlarni tozalash funksiyasi xavfsizlik maqsadida o'chirilgan.",
        show_alert=True,
    )
