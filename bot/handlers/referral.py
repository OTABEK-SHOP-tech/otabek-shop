from html import escape
import logging
import urllib.parse
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from aiogram.exceptions import TelegramBadRequest

from api.config import settings
from db.session import async_session_factory
from bot.keyboards.reply import REFERRAL_BUTTON_TEXT, LEGACY_REFERRAL_BUTTON_TEXT, make_webapp_inline_btn
from bot.services.referral_service import (
    get_user_referral_stats,
    confirm_referral,
    get_channel_info,
)
from bot.services.subscription import (
    check_dual_subscription,
    get_subscription_markup,
    SUBSCRIBE_PROMPT_TEXT,
    is_user_admin,
)

logger = logging.getLogger(__name__)
router = Router(name="referral_participant")
router.message.filter(F.chat.type == "private")


async def render_referral_dashboard(target: Message, user_id: int, is_edit: bool = False):
    """Renders the 20% referral reward dashboard for the user."""
    bot = target.bot
    bot_me = await bot.get_me()

    async with async_session_factory() as session:
        stats = await get_user_referral_stats(session, user_id, bot_me.username)

    confirmed = stats["confirmed_count"]
    needed = stats["friends_needed_for_next"]
    ref_link = stats["referral_link"]
    available_coupons = stats["available_coupons"]
    used_coupons = stats["used_coupons"]
    recent_invites = stats["recent_invites"]

    # Coupon lines
    coupons_lines = []
    if available_coupons:
        coupons_lines.append("\n🎟 <b>Mavjud 20% chegirma kuponlaringiz:</b>")
        for cp in available_coupons:
            if cp.get("is_valid", True):
                coupons_lines.append(f"• <code>{cp['code']}</code> — <b>20% CHEGIRMA</b> (✅ Faol)")
            else:
                coupons_lines.append(f"• <code>{cp['code']}</code> — <i>(Faollashtirish uchun {cp['milestone']} ta do'st kerak)</i>")
        coupons_lines.append("<i>💡 Savatda buyurtma berayotganda ushbu kupon kodini kiriting!</i>")
    else:
        coupons_lines.append(
            "\n🎟 <b>Chegirma kuponlari:</b>\n"
            "<i>Hozircha kuponlaringiz yo'q. 5 ta do'stingizni taklif qiling va "
            "hohlagan 1 ta tovaringizga birinchi 20% chegirma kuponingizni oling! 🌸</i>"
        )

    # Used coupons summary
    if used_coupons:
        coupons_lines.append(f"\n🧾 <i>Ilgari ishlatilgan kuponlar: {len(used_coupons)} ta</i>")

    # Recent invites lines
    inv_lines = []
    if recent_invites:
        status_map = {
            "confirmed": "✅ A'zo bo'ldi",
            "pending": "⏳ Obuna kutilmoqda",
            "revoked": "❌ Chiqib ketgan",
            "was_member_before": "⚠️ Avval a'zo bo'lgan (hisoblanmaydi)",
        }
        inv_lines.append("\n<b>So'nggi takliflaringiz:</b>")
        for inv in recent_invites[:5]:
            badge = "⚠️ Avval a'zo bo'lgan (hisoblanmaydi)" if inv.get("was_member_before") else status_map.get(inv["status"], inv["status"])
            inv_lines.append(f"• {escape(str(inv['name']))} — {badge}")

    # Share URL
    share_text = (
        "🌸 Moonlight Chinese Shop go'zal do'koniga taklif qilaman! ✨\n"
        "Xitoy brendlari, aesthetic kiyimlar va aksessuarlar 🛍️\n\n"
        f"Kanalga a'zo bo'ling: {ref_link}"
    )
    share_url = f"https://t.me/share/url?url={urllib.parse.quote(ref_link)}&text={urllib.parse.quote(share_text)}"

    text = (
        "🌙 <b>DO'STLARNI TAKLIF QILISH — 20% CHEGIRMA</b> 🎁\n\n"
        "Har <b>5 ta do'st</b> taklif qilganingizda, do'kondagi hohlagan <b>1 dona tovaringizga 20% CHEGIRMA</b> kuponiga ega bo'lasiz! 🌸\n\n"
        "✨ <b>Bosqichlar (cheksiz):</b>\n"
        "• 5 ta do'st = 1 ta tovaringizga 20% chegirma 🎟\n"
        "• 10 ta do'st = 2-tovaringizga 20% chegirma 🎟\n"
        "• 15 ta do'st = 3-tovaringizga 20% chegirma 🎟\n"
        "<i>(har qo'shilgan 5 ta yangi do'st uchun yangi 20% lik kupon!)</i>\n\n"
        f"📊 <b>Sizning ko'rsatkichlaringiz:</b>\n"
        f"👥 A'zo bo'lgan do'stlaringiz: <b>{confirmed} ta</b>\n"
        f"⏳ Keyingi 20% lik kupongacha: <b>{needed} ta do'st qoldi</b>\n"
        + "\n".join(coupons_lines)
        + "\n\n"
        f"🔗 <b>Sizning shaxsiy taklif havolangiz:</b>\n<code>{ref_link}</code>\n"
        + "\n".join(inv_lines)
    )

    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📤 Do'stlarga ulashish", url=share_url),
            ],
            [
                make_webapp_inline_btn("🛍️ Do'konni ochish (Mini App)", settings.WEBAPP_URL),
                InlineKeyboardButton(text="🔄 Yangilash", callback_data="refresh_ref_stats"),
            ],
        ]
    )

    if is_edit:
        try:
            await target.edit_text(text, reply_markup=markup)
        except TelegramBadRequest as e:
            if "message is not modified" not in str(e):
                raise
    else:
        await target.answer(text, reply_markup=markup)


@router.message(F.text.in_({REFERRAL_BUTTON_TEXT, LEGACY_REFERRAL_BUTTON_TEXT}))
@router.message(Command("referral", "taklif", "kupon", "chegirma"))
async def handle_referral_menu(message: Message):
    """Handles referral dashboard entry from reply keyboard or command."""
    user_id = message.from_user.id if message.from_user else 0
    async with async_session_factory() as session:
        if not await is_user_admin(session, user_id):
            is_ch, is_chat, ch_url, chat_url = await check_dual_subscription(message.bot, session, user_id)
            if not (is_ch and is_chat):
                await message.answer(
                    SUBSCRIBE_PROMPT_TEXT,
                    reply_markup=get_subscription_markup(ch_url, chat_url, context="referral"),
                )
                return

    await render_referral_dashboard(message, user_id, is_edit=False)


@router.callback_query(F.data == "refresh_ref_stats")
async def handle_refresh_ref_stats(call: CallbackQuery):
    """Refreshes the referral dashboard with live database counts."""
    await render_referral_dashboard(call.message, call.from_user.id, is_edit=True)
    await call.answer("Ko'rsatkichlar yangilandi ✅")


@router.callback_query(F.data.startswith("confirm_ref:"))
async def handle_confirm_referral_callback(call: CallbackQuery):
    """
    Invitee clicked ✅ Tasdiqlash on a referral invite.
    Callback data: confirm_ref:<referrer_id>:<invitee_id>
    """
    parts = call.data.split(":")
    if len(parts) < 3:
        await call.answer("Noto'g'ri so'rov ❌", show_alert=True)
        return

    referrer_id = int(parts[1])
    invitee_id = int(parts[2])

    if call.from_user.id != invitee_id:
        await call.answer("Bu tugma faqat taklif qilingan foydalanuvchi uchun 🌸", show_alert=True)
        return

    bot = call.bot
    bot_me = await bot.get_me()

    async with async_session_factory() as session:
        result = await confirm_referral(
            session=session,
            bot=bot,
            invitee_id=invitee_id,
            referrer_id=referrer_id,
            bot_username=bot_me.username,
        )

    status = result.get("status")
    msg = result.get("message", "")

    if status == "throttled":
        await call.answer(msg, show_alert=True)
        return

    if status == "not_subscribed":
        async with async_session_factory() as session:
            _, ch_url = await get_channel_info(session)

        markup = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="📢 Kanalga o'tish", url=ch_url)],
                [InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"confirm_ref:{referrer_id}:{invitee_id}")],
            ]
        )
        await call.answer(msg, show_alert=True)
        try:
            await call.message.edit_text(
                "🙈 <b>Siz hali kanalga a'zo bo'lmadingiz!</b>\n\n"
                "Iltimos, avval rasmiy kanalimizga obuna bo'ling va keyin <b>✅ Tasdiqlash</b> tugmasini bosing 🌸",
                reply_markup=markup,
            )
        except Exception:
            pass
        return

    if status in ("success", "was_member_before"):
        personal_link = result.get("personal_link", "")
        share_text = (
            "🌸 Moonlight Chinese Shop ga taklif qilaman! ✨\n"
            "Xitoy brendlari, kiyimlar va aksessuarlar 🛍️\n\n"
            f"Kanalga a'zo bo'ling: {personal_link}"
        )
        share_url = f"https://t.me/share/url?url={urllib.parse.quote(personal_link)}&text={urllib.parse.quote(share_text)}"

        markup = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="📤 Do'stlarga ulashish", url=share_url),
                ],
                [
                    make_webapp_inline_btn("🛍️ Do'konni ochish (Mini App)", settings.WEBAPP_URL),
                ],
            ]
        )

        await call.answer("Tasdiqlandi! 🌸", show_alert=False)
        try:
            await call.message.edit_text(
                f"🎉 <b>{msg}</b>\n\n"
                f"🔗 <b>Sizning shaxsiy taklif havolangiz:</b>\n<code>{personal_link}</code>\n\n"
                "Ushbu havolani do'stlaringizga yuboring. Har <b>5 ta do'stingiz</b> uchun hohlagan "
                "1 dona tovaringizga <b>20% CHEGIRMA</b> kuponiga ega bo'lasiz! 💗",
                reply_markup=markup,
            )
        except Exception:
            pass
        return

    await call.answer(msg, show_alert=True)
