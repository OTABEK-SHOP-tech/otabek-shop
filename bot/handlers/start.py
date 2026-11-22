from html import escape
import logging
from datetime import datetime, timezone
from pathlib import Path
from aiogram import Router, F
from aiogram.filters import CommandStart, CommandObject
from aiogram.types import Message, CallbackQuery, FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from sqlalchemy import select

from api.config import settings
from api.services.formatters import format_price, calculate_cargo, strip_private_pricing_data
from bot.keyboards.reply import get_main_reply_keyboard, make_webapp_inline_btn
from bot.services.premium_emojis import upgrade_to_premium_emojis, strip_custom_emojis
from bot.services.subscription import (
    check_dual_subscription,
    get_subscription_markup,
    SUBSCRIBE_PROMPT_TEXT,
    is_user_admin,
    DEFAULT_CHANNEL_URL,
    DEFAULT_CHAT_URL,
)
from db.models import User, Admin, Setting, Product, Review
from db.session import async_session_factory

router = Router(name="start")
router.message.filter(F.chat.type == "private")
logger = logging.getLogger(__name__)


async def send_welcome_greeting(target: Message, user_id: int):
    """Sends the official Moonlight store banner, text and Mini App button."""
    banner_path = Path(settings.MEDIA_CACHE_DIR) / "bot_banner.png"
    channel_link = DEFAULT_CHANNEL_URL
    chat_link = DEFAULT_CHAT_URL
    contact_user = "MOONLIGHT_ADMINNN"

    try:
        async with async_session_factory() as session:
            ch_s = await session.execute(select(Setting).where(Setting.key == "channel_url"))
            ch_obj = ch_s.scalars().first()
            if ch_obj and ch_obj.value:
                channel_link = ch_obj.value

            ct_chat = await session.execute(select(Setting).where(Setting.key == "chat_url"))
            chat_obj = ct_chat.scalars().first()
            if chat_obj and chat_obj.value:
                chat_link = chat_obj.value

            ct_s = await session.execute(select(Setting).where(Setting.key == "contact_username"))
            ct_obj = ct_s.scalars().first()
            if ct_obj and ct_obj.value:
                contact_user = ct_obj.value.strip()
    except Exception:
        pass

    contact_display = contact_user if (contact_user.startswith("+") or contact_user.isdigit()) else f"@{contact_user.lstrip('@')}"
    contact_link = f"https://t.me/{contact_user}" if contact_user.startswith("+") else f"https://t.me/{contact_user.lstrip('@')}"

    raw_greeting_text = (
        "🌙 <b>Moonlight Chinese Shop ga xush kelibsiz!</b> ✨\n\n"
        "Xitoy brendlari va aesthetic kiyimlar, jempirlar, pariklar va nozik aksessuarlar do'koni 🛍️\n\n"
        "🛍️ <b>Do'konni ochish</b> tugmasini bosib, barcha go'zal mahsulotlarni qulay Mini App orqali tomosha qiling va savatga qo'shing!\n\n"
        "📍 Toshkent | 🚚 O'zbekiston bo'ylab yetkazib berish\n"
        f"💌 Savollar va buyurtma uchun: {contact_display}"
    )
    greeting_text = upgrade_to_premium_emojis(raw_greeting_text)

    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [make_webapp_inline_btn("🛍️ Do'konni ochish", settings.WEBAPP_URL)],
            [
                InlineKeyboardButton(text="📢 Rasmiy kanal", url=channel_link),
                InlineKeyboardButton(text="💬 Rasmiy guruh", url=chat_link),
            ],
            [
                InlineKeyboardButton(text="💌 Bog'lanish", url=contact_link),
            ]
        ]
    )

    plain_webapp_btn = (
        InlineKeyboardButton(text="🛍️ Do'konni ochish", web_app=WebAppInfo(url=settings.WEBAPP_URL))
        if (settings.WEBAPP_URL and settings.WEBAPP_URL.startswith("https://"))
        else InlineKeyboardButton(text="🛍️ Do'konni ochish", url="https://t.me/moonlight_chinese_shop")
    )
    plain_markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [plain_webapp_btn],
            [
                InlineKeyboardButton(text="📢 Rasmiy kanal", url=channel_link),
                InlineKeyboardButton(text="💬 Rasmiy guruh", url=chat_link),
            ],
            [
                InlineKeyboardButton(text="💌 Bog'lanish", url=contact_link),
            ],
        ]
    )

    if banner_path.is_file():
        photo_sent = False
        try:
            await target.answer_photo(
                photo=FSInputFile(str(banner_path)),
                caption=greeting_text,
                reply_markup=markup,
            )
            photo_sent = True
        except Exception:
            try:
                await target.answer_photo(
                    photo=FSInputFile(str(banner_path)),
                    caption=strip_custom_emojis(raw_greeting_text),
                    reply_markup=plain_markup,
                )
                photo_sent = True
            except Exception:
                photo_sent = False

        if photo_sent:
            await target.answer(
                "👇 Quyidagi menyudan kerakli bo'limni tanlang (20% chegirma taklif tizimi va konkurs shu yerda) ✨",
                reply_markup=get_main_reply_keyboard(),
            )
            return

    await target.answer(strip_custom_emojis(raw_greeting_text), reply_markup=get_main_reply_keyboard())


async def _check_dual_sub_or_prompt(message: Message) -> bool:
    """Returns True if user is subscribed to both channel and chat (or is admin). Sends prompt and returns False otherwise."""
    user_id = message.from_user.id
    async with async_session_factory() as session:
        if await is_user_admin(session, user_id):
            return True
        is_ch, is_chat, ch_url, chat_url = await check_dual_subscription(message.bot, session, user_id)
        if not (is_ch and is_chat):
            await message.answer(
                SUBSCRIBE_PROMPT_TEXT,
                reply_markup=get_subscription_markup(ch_url, chat_url),
            )
            return False
    return True


async def send_product_deep_link(message: Message, prod_id: int) -> bool:
    """Renders and sends a product card with interactive Mini App link and photo."""
    try:
        async with async_session_factory() as session:
            res_p = await session.execute(select(Product).where(Product.id == prod_id))
            product = res_p.scalars().first()
            if not product:
                return False

            product.views += 1
            await session.commit()

            cargo = calculate_cargo(product.weight_grams)
            clean_title = strip_private_pricing_data(product.title) or product.title
            clean_desc = strip_private_pricing_data(product.description or "")
            desc_text = f"\n\n{escape(str(clean_desc))}" if clean_desc else ""
            stock_badge = "" if product.in_stock else "\n\n❌ <b>Sotildi (Hozirda mavjud emas)</b>"

            contact_val = "MOONLIGHT_ADMINNN"
            try:
                c_s = await session.execute(select(Setting).where(Setting.key == "contact_username"))
                c_row = c_s.scalars().first()
                if c_row and c_row.value:
                    contact_val = c_row.value.strip()
            except Exception:
                pass
            contact_display = contact_val if (contact_val.startswith("+") or contact_val.isdigit()) else f"@{contact_val.lstrip('@')}"
            contact_link = f"https://t.me/{contact_val}" if contact_val.startswith("+") else f"https://t.me/{contact_val.lstrip('@')}"

            webapp_url = settings.WEBAPP_URL or "https://bek-style-shop.onrender.com"
            is_https_webapp = bool(webapp_url and webapp_url.startswith("https://"))

            prompt_action = (
                "🛍️ <b>Mahsulotni sotib olish uchun pastdagi tugmani bosing:</b>\n"
                if is_https_webapp
                else ""
            )

            text = (
                f"🌙 <b>{escape(str(clean_title))}</b>\n"
                f"💰 <b>Narxi:</b> {format_price(product.price)}\n"
                f"🌸 <b>Kargo (100g):</b> AVIA 14.000 | AVTO 10.000 (Kargo uchun alohida to'lov qilinadi)\n"
                f"{desc_text}"
                f"{stock_badge}\n\n"
                f"{prompt_action}"
                f"💌 Buyurtma yoki savollar uchun: {contact_display}"
            )

            buttons = []
            if is_https_webapp:
                buttons.append([
                    InlineKeyboardButton(
                        text="🛍️ Mahsulotni xarid qilish (Mini App)",
                        web_app=WebAppInfo(url=f"{webapp_url.rstrip('/')}?product={product.id}"),
                    )
                ])
            buttons.append([
                InlineKeyboardButton(
                    text="💌 Admin bilan bog'lanish (Buyurtma)",
                    url=contact_link,
                )
            ])
            markup = InlineKeyboardMarkup(inline_keyboard=buttons)

            # Send with photo if available
            media_dir = Path(settings.MEDIA_CACHE_DIR)
            if product.photos:
                photo_id = product.photos[0]
                local_file = media_dir / photo_id
                photo_obj = FSInputFile(str(local_file)) if local_file.is_file() else photo_id
                try:
                    await message.answer_photo(photo=photo_obj, caption=text, reply_markup=markup)
                    return True
                except Exception:
                    pass

            await message.answer(text, reply_markup=markup)
            return True
    except Exception as e:
        logger.warning(f"Error rendering product deep link {prod_id}: {e}")
        return False


@router.message(CommandStart())
async def handle_start(message: Message, command: CommandObject):
    user_id = message.from_user.id
    full_name = message.from_user.full_name or "Mijoz"
    username = message.from_user.username
    payload = command.args or ""

    # 1. Update or create user in DB, tracking whether they existed before
    is_new_user = False
    async with async_session_factory() as session:
        now = datetime.now(timezone.utc)
        u_res = await session.execute(select(User).where(User.telegram_id == user_id))
        user_obj = u_res.scalars().first()

        try:
            if not user_obj:
                is_new_user = True
                user_obj = User(
                    telegram_id=user_id,
                    name=full_name,
                    username=username,
                    language="uz",
                    first_seen=now,
                    last_seen=now,
                    blocked_bot=False,
                )
                session.add(user_obj)
            else:
                user_obj.name = full_name
                user_obj.username = username
                user_obj.last_seen = now
                user_obj.blocked_bot = False

            await session.commit()
        except Exception:
            await session.rollback()
            is_new_user = False
            u_res2 = await session.execute(select(User).where(User.telegram_id == user_id))
            user_obj2 = u_res2.scalars().first()
            if user_obj2:
                user_obj2.name = full_name
                user_obj2.username = username
                user_obj2.last_seen = now
                await session.commit()

    # 2. Check for OWNER CLAIM deep link: /start claim_<CODE> (Allowed without prior subscription)
    if payload.startswith("claim_"):
        from bot.services.ownership import claim_ownership

        async with async_session_factory() as session:
            result = await claim_ownership(session, payload[6:], user_id, full_name, username)

        if result == "already_owner":
            await message.answer(
                "🌸 <b>Siz allaqachon do'kon egasisiz!</b>\n"
                "Boshqaruv menyusini ochish uchun /admin buyrug'ini bosing.",
                reply_markup=get_main_reply_keyboard(),
            )
            return

        if result == "invalid":
            await message.answer(
                "❌ <b>Bu havola yaroqsiz yoki allaqachon ishlatilgan.</b>\n"
                "Yangi havolani do'kon egasidan so'rang 🌸",
                reply_markup=get_main_reply_keyboard(),
            )
            return

        if result == "claimed":
            owner_welcome = (
                "🌙 <b>Bu do'kon endi sizniki / This shop is now yours</b> 🛍️\n\n"
                "Tabriklaymiz! Siz <b>Moonlight Chinese Shop</b>ning rasmiy egasi etib tayinlandingiz.\n\n"
                "✨ <b>Qisqa qo'llanma (3 ta qadam):</b>\n"
                "1️⃣ <b>Yangi mahsulot:</b> /admin buyrug'ini bosing yoki Mini App ichidagi 👑 Admin tugmasidan foydalaning.\n"
                "2️⃣ <b>Kanalni ulash:</b> Botni o'z kanalingizga admin qilib qo'shing — bot avtomatik aniqlaydi va tasdiqlashingiz bilan ulaydi.\n"
                "3️⃣ <b>Buyurtmalar:</b> Mijozlar do'kondan buyurtma berishi bilan bu yerga chiroyli xabar bo'lib keladi.\n\n"
                "Boshqaruv menyusini ochish uchun <b>/admin</b> buyrug'ini bosing! 💗"
            )
            await message.answer(owner_welcome, reply_markup=get_main_reply_keyboard())
            return

    # 3. MANDATORY SUBSCRIPTION CHECK (Channel + Chat)
    # Check if user is an admin or subscribed to both channel and chat
    if not payload.startswith("r_") and not payload.startswith("ref_"):
        async with async_session_factory() as session:
            if not await is_user_admin(session, user_id):
                is_ch, is_chat, ch_url, chat_url = await check_dual_subscription(message.bot, session, user_id)
                if not (is_ch and is_chat):
                    sub_context = payload if payload else None
                    await message.answer(
                        SUBSCRIBE_PROMPT_TEXT,
                        reply_markup=get_subscription_markup(ch_url, chat_url, context=sub_context),
                    )
                    return

    # Check for REFERRAL direct link: /start referral or /start taklif
    if payload in ("referral", "taklif", "kupon"):
        from bot.handlers.referral import render_referral_dashboard
        await render_referral_dashboard(message, user_id)
        return

    # Check for CONTEST direct link: /start konkurs
    if payload == "konkurs":
        from bot.handlers.contest import show_user_contest_dashboard
        await show_user_contest_dashboard(message, user_id)
        return

    # Check for 20% DISCOUNT REFERRAL deep link: /start ref_<referrer_id>
    if payload.startswith("ref_"):
        try:
            referrer_id = int(payload[4:])
        except ValueError:
            referrer_id = 0

        if not referrer_id:
            if not await _check_dual_sub_or_prompt(message):
                return

        if referrer_id:
            from bot.services.referral_service import process_referral_start, get_user_referral_link
            async with async_session_factory() as session:
                ref_result = await process_referral_start(
                    session=session,
                    bot=message.bot,
                    invitee_id=user_id,
                    invitee_full_name=full_name,
                    invitee_username=username,
                    is_bot=message.from_user.is_bot or False,
                    referrer_id=referrer_id,
                    is_new_user=is_new_user,
                )

                if not ref_result.get("valid"):
                    reason = ref_result.get("reason")
                    if reason in ("existing_user", "already_referred_by_other"):
                        if not await _check_dual_sub_or_prompt(message):
                            return
                        await message.answer(
                            ref_result.get("message"),
                            reply_markup=get_main_reply_keyboard(),
                        )
                        return
                    # Malformed, self, or bot payloads must still pass mandatory dual subscription gate
                    if not await _check_dual_sub_or_prompt(message):
                        return
                else:
                    channel_url = ref_result.get("channel_url", "https://t.me/moonlight_chinese_shop")
                    was_member_before = ref_result.get("was_member_before", False)

                    bot_me = await message.bot.get_me()
                    personal_link = get_user_referral_link(bot_me.username, user_id)

                    ref_obj = ref_result.get("referral")
                    if ref_obj and ref_obj.status == "confirmed":
                        markup = InlineKeyboardMarkup(
                            inline_keyboard=[
                                [InlineKeyboardButton(text="👥 Mening taklif havolam", callback_data="refresh_ref_stats")],
                                [make_webapp_inline_btn("🌸 Do'konni ochish", settings.WEBAPP_URL)],
                            ]
                        )
                        await message.answer(
                            "🌸 <b>Siz allaqachon ushbu taklif orqali kanalimizga a'zo bo'lgansiz!</b> 🎀\n\n"
                            "Endi siz ham o'z do'stlaringizni taklif qilib, "
                            "har <b>5 ta do'stingiz uchun 20% CHEGIRMA</b> kuponiga ega bo'lishingiz mumkin! 🎁\n\n"
                            f"🔗 <b>Sizning shaxsiy taklif havolangiz:</b>\n<code>{personal_link}</code>",
                            reply_markup=markup,
                        )
                        return

                    if was_member_before:
                        markup = InlineKeyboardMarkup(
                            inline_keyboard=[
                                [InlineKeyboardButton(text="👥 Mening taklif havolam", callback_data="refresh_ref_stats")],
                                [make_webapp_inline_btn("🌸 Do'konni ochish", settings.WEBAPP_URL)],
                            ]
                        )
                        await message.answer(
                            "🌸 <b>Siz allaqachon kanalimiz a'zosisiz!</b> 🎀\n\n"
                            "Do'stingizga taklif balli hisoblanmadi, lekin siz ham o'z do'stlaringizni taklif qilib, "
                            "har <b>5 ta do'stingiz uchun 20% CHEGIRMA</b> kuponiga ega bo'lishingiz mumkin! 🎁\n\n"
                            f"🔗 <b>Sizning shaxsiy taklif havolangiz:</b>\n<code>{personal_link}</code>",
                            reply_markup=markup,
                        )
                        return

                    # Normal new invitee flow: show subscription prompt
                    markup = InlineKeyboardMarkup(
                        inline_keyboard=[
                            [InlineKeyboardButton(text="📢 Kanalga o'tish", url=channel_url)],
                            [InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"confirm_ref:{referrer_id}:{user_id}")],
                        ]
                    )
                    await message.answer(
                        "🌸 <b>Moonlight Chinese Shop ga xush kelibsiz!</b> 🎀\n\n"
                        "Do'stingiz taklifi bilan kirdingiz. Botdan foydalanish va do'stingizga ball hisoblanishi uchun "
                        "rasmiy kanalimizga a'zo bo'ling va quyidagi <b>✅ Tasdiqlash</b> tugmasini bosing:",
                        reply_markup=markup,
                    )
                    return

    # Check for CONTEST REFERRAL deep link: /start r_<contest_id>_<referrer_id>
    if payload.startswith("r_"):
        from bot.services.contest_service import process_referral_start, get_channel_info
        async with async_session_factory() as session:
            ref_result = await process_referral_start(
                session=session,
                bot=message.bot,
                user_id=user_id,
                user_full_name=full_name,
                user_username=username,
                is_bot=message.from_user.is_bot or False,
                payload=payload,
                is_new_user=is_new_user,
            )

            if not ref_result.get("valid"):
                reason = ref_result.get("reason")
                if reason == "no_active_contest":
                    if not await _check_dual_sub_or_prompt(message):
                        return
                    await message.answer(
                        "🌸 <b>Hozircha faol konkurs yo'q</b> 🎀\nLekin do'konimizdan bahramand bo'lishingiz mumkin!",
                        reply_markup=get_main_reply_keyboard(),
                    )
                    return
                elif reason == "existing_user":
                    if not await _check_dual_sub_or_prompt(message):
                        return
                    await message.answer(
                        ref_result.get("message"),
                        reply_markup=get_main_reply_keyboard(),
                    )
                    return
                # Malformed, self, or invalid payloads must still pass mandatory dual subscription gate
                if not await _check_dual_sub_or_prompt(message):
                    return
            else:
                contest = ref_result["contest"]
                channel_url = ref_result.get("channel_url", "https://t.me/moonlight_chinese_shop")
                was_member_before = ref_result.get("was_member_before", False)

                if was_member_before and contest.only_new_subscribers:
                    bot_me = await message.bot.get_me()
                    personal_link = f"https://t.me/{bot_me.username}?start=r_{contest.id}_{user_id}"
                    markup = InlineKeyboardMarkup(
                        inline_keyboard=[
                            [InlineKeyboardButton(text="🎁 Konkursda qatnashish", callback_data=f"my_stats:{contest.id}")],
                            [make_webapp_inline_btn("🌸 Do'konni ochish", settings.WEBAPP_URL)],
                        ]
                    )
                    await message.answer(
                        "🌸 <b>Siz allaqachon kanalimiz a'zosisiz!</b> 🎀\n\n"
                        "Do'stingizga taklif balli hisoblanmadi, lekin siz ham konkursda qatnashib, qimmatbaho sovg'alarni yutib olishingiz mumkin! 🎁\n\n"
                        f"🔗 <b>Sizning shaxsiy taklif havolangiz:</b>\n<code>{personal_link}</code>",
                        reply_markup=markup,
                    )
                    return

                # Normal new invitee flow: show subscription prompt
                markup = InlineKeyboardMarkup(
                    inline_keyboard=[
                        [InlineKeyboardButton(text="📢 Kanalga o'tish", url=channel_url)],
                        [InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"confirm_sub:{contest.id}:{user_id}")],
                    ]
                )
                await message.answer(
                    "🌸 <b>Konkursda qatnashish uchun kanalga obuna bo'ling</b> 🎀\n\n"
                    "Kanalimizga a'zo bo'ling va quyidagi <b>✅ Tasdiqlash</b> tugmasini bosing:",
                    reply_markup=markup,
                )
                return

    # 4. Check for PRODUCT deep link: /start product_<ID>
    if payload.startswith("product_"):
        try:
            prod_id = int(payload[8:])
            if await send_product_deep_link(message, prod_id):
                return
        except Exception as e:
            logger.warning(f"Error handling product deep link: {e}")

    # 5. Standard welcome message
    await send_welcome_greeting(message, user_id)


# Fast reply button handlers — all require dual subscription
@router.message(F.text == "🆕 Yangi mahsulotlar")
async def handle_new_products(message: Message):
    if not await _check_dual_sub_or_prompt(message):
        return
    async with async_session_factory() as session:
        res = await session.execute(
            select(Product).where(Product.is_new == True, Product.in_stock == True).limit(5)
        )
        prods = res.scalars().all()
        if not prods:
            await message.answer("🌸 Hozircha yangi mahsulotlar kutilmoqda. Do'konni ochib barcha modellarni ko'rishingiz mumkin!")
            return

        lines = ["🌸 <b>Yangi mahsulotlar:</b>\n"]
        for p in prods:
            clean_p_title = strip_private_pricing_data(p.title) or p.title
            lines.append(f"• <b>{escape(str(clean_p_title))}</b> — {format_price(p.price)}")
        lines.append(f"\n🛍️ Do'konni ochish tugmasini bosing:")

        markup = InlineKeyboardMarkup(
            inline_keyboard=[
                [make_webapp_inline_btn("🌸 Do'konni ochish", f"{settings.WEBAPP_URL}?tab=new")]
            ]
        )
        await message.answer("\n".join(lines), reply_markup=markup)


@router.message(F.text == "⭐ Fikrlar")
async def handle_reviews(message: Message):
    if not await _check_dual_sub_or_prompt(message):
        return
    async with async_session_factory() as session:
        res = await session.execute(
            select(Review).where(Review.approved == True).order_by(Review.created_at.desc()).limit(3)
        )
        revs = res.scalars().all()
        if not revs:
            await message.answer("🌸 Mijozlarimiz fikrlari tez orada bu yerda ko'rinadi!")
            return

        lines = ["⭐ <b>Mijozlarimizdan fikrlar (#отзыв):</b>\n"]
        for r in revs:
            lines.append(f"💬 <i>\"{escape(str(r.text))}\"</i>\n   — <b>{escape(str(r.customer_name))}</b>\n")

        markup = InlineKeyboardMarkup(
            inline_keyboard=[
                [make_webapp_inline_btn("🌸 Barcha fikrlar Mini App'da", f"{settings.WEBAPP_URL}?tab=reviews")]
            ]
        )
        await message.answer("\n".join(lines), reply_markup=markup)


@router.message(F.text == "💌 Admin bilan bog'lanish")
async def handle_contact(message: Message):
    if not await _check_dual_sub_or_prompt(message):
        return
    contact_val = "MOONLIGHT_ADMINNN"
    try:
        async with async_session_factory() as session:
            ct_s = await session.execute(select(Setting).where(Setting.key == "contact_username"))
            ct_obj = ct_s.scalars().first()
            if ct_obj and ct_obj.value:
                contact_val = ct_obj.value.strip()
    except Exception:
        pass
    contact_display = contact_val if (contact_val.startswith("+") or contact_val.isdigit()) else f"@{contact_val.lstrip('@')}"
    contact_link = f"https://t.me/{contact_val}" if contact_val.startswith("+") else f"https://t.me/{contact_val.lstrip('@')}"
    await message.answer(
        f"🌙 Har qanday savol va buyurtma uchun to'g'ridan-to'g'ri {contact_display} ga yozishingiz mumkin! 💌",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=f"💌 {contact_display} ga yozish", url=contact_link)]
            ]
        ),
    )


@router.message(F.text == "📢 Kanal")
async def handle_channel_link(message: Message):
    if not await _check_dual_sub_or_prompt(message):
        return
    channel_link = DEFAULT_CHANNEL_URL
    chat_link = DEFAULT_CHAT_URL
    try:
        async with async_session_factory() as session:
            ch_s = await session.execute(select(Setting).where(Setting.key == "channel_url"))
            ch_obj = ch_s.scalars().first()
            if ch_obj and ch_obj.value:
                channel_link = ch_obj.value

            ct_chat = await session.execute(select(Setting).where(Setting.key == "chat_url"))
            chat_obj = ct_chat.scalars().first()
            if chat_obj and chat_obj.value:
                chat_link = chat_obj.value
    except Exception:
        pass

    await message.answer(
        f"🌙 Bizning rasmiy Telegram kanalimiz va guruhimizga a'zo bo'ling va yangi kolleksiyalarni birinchi bo'lib ko'ring!\n\n"
        f"📢 <b>Kanal:</b> {channel_link}\n"
        f"💬 <b>Guruh:</b> {chat_link}",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="📢 Kanalga o'tish", url=channel_link)],
                [InlineKeyboardButton(text="💬 Guruhga o'tish", url=chat_link)],
            ]
        ),
    )


# --- FORCED DUAL SUBSCRIPTION: "Obuna bo'ldim" / "Tasdiqlash" callback handler ---
@router.callback_query(F.data == "check_subscription")
@router.callback_query(F.data.startswith("check_sub:"))
@router.callback_query(F.data.startswith("check_subscription:"))
async def handle_subscription_confirm(callback: CallbackQuery):
    user_id = callback.from_user.id
    raw_data = callback.data or ""
    context = None
    if raw_data.startswith("check_sub:"):
        context = raw_data[len("check_sub:"):]
    elif raw_data.startswith("check_subscription:"):
        context = raw_data[len("check_subscription:"):]

    async with async_session_factory() as session:
        if await is_user_admin(session, user_id):
            is_ch, is_chat = True, True
            ch_url, chat_url = DEFAULT_CHANNEL_URL, DEFAULT_CHAT_URL
        else:
            is_ch, is_chat, ch_url, chat_url = await check_dual_subscription(callback.bot, session, user_id)

    if is_ch and is_chat:
        await callback.answer("✅ Rahmat! Obuna muvaffaqiyatli tasdiqlandi!", show_alert=False)
        try:
            await callback.message.delete()
        except Exception:
            pass

        # If user arrived via deep link, open their target product / contest card immediately!
        if context:
            if context.startswith("product_"):
                try:
                    prod_id = int(context[8:])
                    sent = await send_product_deep_link(callback.message, prod_id)
                    if sent:
                        return
                except Exception as e:
                    logger.warning(f"Error displaying deep-linked product after subscription: {e}")
            elif context == "konkurs" or context.startswith("konkurs_"):
                try:
                    from bot.handlers.contest import show_user_contest_dashboard
                    await show_user_contest_dashboard(callback.message, user_id)
                    return
                except Exception as e:
                    logger.warning(f"Error displaying contest dashboard after subscription: {e}")
            elif context in ("referral", "taklif", "kupon"):
                try:
                    from bot.handlers.referral import render_referral_dashboard
                    await render_referral_dashboard(callback.message, user_id)
                    return
                except Exception as e:
                    logger.warning(f"Error displaying referral dashboard after subscription: {e}")

        await send_welcome_greeting(callback.message, user_id)
    elif not is_ch and not is_chat:
        await callback.answer(
            "❌ Siz hali kanal va guruhimizga a'zo bo'lmadingiz!\nIltimos, ikkalasiga ham a'zo bo'ling.",
            show_alert=True,
        )
    elif not is_ch:
        await callback.answer(
            "⚠️ Siz kanalimizga hali a'zo bo'lmadingiz!\nIltimos, kanalga a'zo bo'ling.",
            show_alert=True,
        )
    else:
        await callback.answer(
            "⚠️ Siz guruhimizga hali a'zo bo'lmadingiz!\nIltimos, guruhga ham qo'shiling.",
            show_alert=True,
        )


# Backward-compatibility alias
handle_check_subscription = handle_subscription_confirm
