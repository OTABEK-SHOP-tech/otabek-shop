"""Admin panel: menu, stats, settings, admins, channel linking, broadcast."""

import asyncio
import re
from html import escape

from aiogram import Bot, F, Router
from aiogram.enums import ChatMemberStatus, ChatType
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    ChatFullInfo,
    ChatMemberAdministrator,
    ChatMemberUpdated,
    InlineKeyboardMarkup,
    Message,
    MessageOriginUser,
)
from sqlalchemy import delete, select

from bekstyle import texts as t
from bekstyle.db import DEFAULT_SETTINGS, Admin, async_session, get_setting, set_setting
from bekstyle.handlers import IsAdmin, cb_message, menu_for, show_in
from bekstyle.keyboards import admin_menu, inline, reply_kb
from bekstyle.notify import run_broadcast
from bekstyle.services import is_owner, shop_stats, validate_setting

router = Router(name="admin")
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())

ADMIN_TITLE = f"👑 <b>{t.BRAND}</b> · Admin panel"
CHANNEL_RE = re.compile(r"(?:https?://)?(?:t\.me/|@)?([A-Za-z][A-Za-z0-9_]{4,31})/?")
SETTING_PROMPTS: dict[str, str] = {
    "contact_username": "📞 Mijozlar yozadigan username (masalan: <code>@bekstyle_admin</code>):",
    "yuan_rate": "💱 1 yuan necha so'm? (masalan: <code>1800</code>):",
    "markup_percent": "📈 Ustama foizi (masalan: <code>40</code>):",
    "delivery_text": "🚚 Yetkazish muddati (masalan: <code>15–25 kun</code>):",
}
_background: set["asyncio.Task[None]"] = set()  # keeps broadcast tasks alive until they finish


class EditSetting(StatesGroup):
    value = State()


class AddAdmin(StatesGroup):
    target = State()


class LinkChannel(StatesGroup):
    username = State()


class Broadcast(StatesGroup):
    message = State()
    confirm = State()


# ---------- menu & stats ----------
@router.message(Command("admin"))
@router.message(F.text == t.BTN_ADMIN)
async def on_admin(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(f"{ADMIN_TITLE}\nNima qilamiz?", reply_markup=admin_menu())


@router.callback_query(F.data == "a:menu")
async def on_admin_menu(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await show_in(callback, f"{ADMIN_TITLE}\nNima qilamiz?", admin_menu())


@router.callback_query(F.data == "a:stats")
async def on_stats(callback: CallbackQuery) -> None:
    async with async_session() as session:
        s = await shop_stats(session)
    statuses = [f"{t.status_label(st)}: {s.get('orders_' + st, 0)}" for st in [*t.STATUS_FLOW, "cancelled"]]
    text = "\n".join(
        [
            "📊 <b>Statistika</b>",
            t.LINE,
            f"👥 Mijozlar: {s['users']}",
            f"📦 Mahsulotlar: {s['in_stock']} sotuvda / {s['products']} jami",
            t.LINE,
            *statuses,
            t.LINE,
            f"💵 Tasdiqlangan savdo: <b>{t.format_price(s['revenue'])}</b>",
        ]
    )
    await show_in(callback, text, inline([("⬅️ Menyu", "a:menu")]))


# ---------- settings ----------
async def settings_view() -> tuple[str, InlineKeyboardMarkup]:
    async with async_session() as session:
        v = {key: await get_setting(session, key) for key in DEFAULT_SETTINGS}
    channel = (
        f"@{v['channel_username']}" if v["channel_username"] else ("ulangan ✅" if v["channel_id"] else "ulanmagan ❌")
    )
    text = (
        f"⚙️ <b>Sozlamalar</b>\n{t.LINE}\n"
        f"📞 Kontakt: {'@' + v['contact_username'] if v['contact_username'] else '—'}\n"
        f"💱 Kurs: 1¥ = {v['yuan_rate']} so'm\n"
        f"📈 Ustama: {v['markup_percent']}%\n"
        f"🚚 Yetkazish: {escape(v['delivery_text'])}\n"
        f"📢 Kanal: {escape(channel)}"
    )
    markup = inline(
        [("📞 Kontakt", "set:contact_username"), ("💱 Yuan kursi", "set:yuan_rate")],
        [("📈 Ustama %", "set:markup_percent"), ("🚚 Muddat", "set:delivery_text")],
        [("🔗 Kanalni ulash", "ch:link"), ("✂️ Kanalni uzish", "ch:unlink")],
        [("👥 Adminlar", "a:admins"), ("⬅️ Menyu", "a:menu")],
    )
    return text, markup


@router.callback_query(F.data == "a:settings")
async def on_settings(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await show_in(callback, *await settings_view())


@router.callback_query(F.data.startswith("set:"))
async def on_setting_edit(callback: CallbackQuery, state: FSMContext) -> None:
    key = (callback.data or "").split(":", 1)[1]
    msg = cb_message(callback)
    if key not in SETTING_PROMPTS or msg is None:
        await callback.answer()
        return
    await state.set_state(EditSetting.value)
    await state.update_data(key=key)
    await msg.answer(SETTING_PROMPTS[key], reply_markup=reply_kb())
    await callback.answer()


@router.message(EditSetting.value, F.text)
async def on_setting_value(message: Message, state: FSMContext) -> None:
    key = str((await state.get_data()).get("key", ""))
    value = validate_setting(key, message.text or "")
    if value is None:
        await message.answer("⚠️ Noto'g'ri qiymat. " + SETTING_PROMPTS.get(key, ""))
        return
    async with async_session() as session:
        await set_setting(session, key, value)
    await state.clear()
    await message.answer("✅ Saqlandi.", reply_markup=await menu_for(message.chat.id))
    text, markup = await settings_view()
    await message.answer(text, reply_markup=markup)


# ---------- admins ----------
async def admins_view() -> tuple[str, InlineKeyboardMarkup]:
    async with async_session() as session:
        admins = (await session.scalars(select(Admin).order_by(Admin.added_at))).all()
    lines = [f"{'👑' if a.role == 'owner' else '🛠'} {escape(a.name)} · <code>{a.telegram_id}</code>" for a in admins]
    removable = [[(f"🗑 {a.name[:20]}", f"adm:del:{a.telegram_id}")] for a in admins if a.role != "owner"]
    markup = inline(*removable, [("➕ Admin qo'shish", "adm:add"), ("⬅️ Sozlamalar", "a:settings")])
    return f"👥 <b>Adminlar</b>\n{t.LINE}\n" + "\n".join(lines), markup


@router.callback_query(F.data == "a:admins")
async def on_admins(callback: CallbackQuery) -> None:
    await show_in(callback, *await admins_view())


async def _owner_only(callback: CallbackQuery) -> bool:
    async with async_session() as session:
        allowed = await is_owner(session, callback.from_user.id)
    if not allowed:
        await callback.answer("⛔ Buni faqat do'kon egasi qila oladi.", show_alert=True)
    return allowed


@router.callback_query(F.data == "adm:add")
async def on_admin_add(callback: CallbackQuery, state: FSMContext) -> None:
    msg = cb_message(callback)
    if not await _owner_only(callback) or msg is None:
        return
    await state.set_state(AddAdmin.target)
    await msg.answer(
        "➕ <b>Yangi admin</b>\nUning xabarini forward qiling, kontaktini yuboring yoki Telegram ID raqamini yozing.",
        reply_markup=reply_kb(),
    )
    await callback.answer()


def _resolve_target(message: Message) -> tuple[int, str] | None:
    origin = message.forward_origin
    if isinstance(origin, MessageOriginUser):
        return origin.sender_user.id, origin.sender_user.full_name
    if message.contact and message.contact.user_id:
        return message.contact.user_id, message.contact.first_name
    text = (message.text or "").strip()
    return (int(text), "Admin") if re.fullmatch(r"[0-9]{5,15}", text) else None


@router.message(AddAdmin.target)
async def on_admin_target(message: Message, state: FSMContext) -> None:
    target = _resolve_target(message)
    if target is None:
        await message.answer(
            "⚠️ Aniqlab bo'lmadi (profil yashirilgan bo'lishi mumkin). Telegram ID raqamini yozing — "
            "u @userinfobot orqali bilib oladi."
        )
        return
    user_id, name = target
    async with async_session() as session:
        if await session.get(Admin, user_id):
            reply = "ℹ️ Bu foydalanuvchi allaqachon admin."
        else:
            session.add(Admin(telegram_id=user_id, name=name, role="admin"))
            await session.commit()
            reply = f"✅ {escape(name)} admin qilindi. U botda /start bossin — 👑 tugma chiqadi."
    await state.clear()
    await message.answer(reply, reply_markup=await menu_for(message.chat.id))


@router.callback_query(F.data.startswith("adm:del:"))
async def on_admin_delete(callback: CallbackQuery) -> None:
    if not await _owner_only(callback):
        return
    target_id = int((callback.data or "").split(":")[2])
    async with async_session() as session:
        await session.execute(delete(Admin).where(Admin.telegram_id == target_id, Admin.role != "owner"))
        await session.commit()
    await show_in(callback, *await admins_view())


# ---------- channel ----------
async def verify_channel(bot: Bot, chat_ref: int | str, user_id: int) -> tuple[ChatFullInfo | None, str]:
    try:
        chat = await bot.get_chat(chat_ref)
        me = await bot.get_me()
        bot_member = await bot.get_chat_member(chat.id, me.id)
        user_member = await bot.get_chat_member(chat.id, user_id)
    except TelegramAPIError:
        return (
            None,
            "❌ Kanal topilmadi yoki bot u yerda yo'q. Botni kanalga admin qiling.",
        )
    if chat.type != ChatType.CHANNEL:
        return None, "❌ Bu kanal emas."
    if not isinstance(bot_member, ChatMemberAdministrator) or not bot_member.can_post_messages:
        return None, "❌ Botga «Post joylash» huquqi bilan admin bering."
    if user_member.status not in (
        ChatMemberStatus.CREATOR,
        ChatMemberStatus.ADMINISTRATOR,
    ):
        return None, "❌ Siz bu kanalda admin emassiz."
    return chat, ""


async def _save_channel(chat: ChatFullInfo) -> str:
    async with async_session() as session:
        await set_setting(session, "channel_id", str(chat.id))
        await set_setting(session, "channel_username", chat.username or "")
    return f"✅ <b>{escape(chat.title or 'Kanal')}</b> ulandi. Endi mahsulotni 1 bosishda kanalga joylaysiz 📢"


@router.my_chat_member(F.chat.type == ChatType.CHANNEL)
async def on_bot_channel_status(event: ChatMemberUpdated, bot: Bot) -> None:
    status = event.new_chat_member.status
    async with async_session() as session:
        if status == ChatMemberStatus.ADMINISTRATOR and await is_owner(session, event.from_user.id):
            await bot.send_message(
                event.from_user.id,
                f"📢 <b>{escape(event.chat.title or 'Kanal')}</b> aniqlandi. Do'konga ulaymi?",
                reply_markup=inline([("✅ Ha, ulash", f"chy:{event.chat.id}"), ("❌ Yo'q", "chn")]),
            )
        elif status in (
            ChatMemberStatus.LEFT,
            ChatMemberStatus.KICKED,
        ) and await get_setting(session, "channel_id") == str(event.chat.id):
            await set_setting(session, "channel_id", "")
            await set_setting(session, "channel_username", "")


@router.callback_query(F.data.startswith("chy:"))
async def on_channel_confirm(callback: CallbackQuery, bot: Bot) -> None:
    if not await _owner_only(callback):
        return
    chat, error = await verify_channel(bot, int((callback.data or "").split(":")[1]), callback.from_user.id)
    if chat is None:
        await callback.answer(error, show_alert=True)
        return
    await show_in(callback, await _save_channel(chat))


@router.callback_query(F.data == "chn")
async def on_channel_decline(callback: CallbackQuery) -> None:
    await show_in(callback, "Kanal ulanmadi.")


@router.callback_query(F.data == "ch:link")
async def on_channel_link(callback: CallbackQuery, state: FSMContext) -> None:
    msg = cb_message(callback)
    if not await _owner_only(callback) or msg is None:
        return
    await state.set_state(LinkChannel.username)
    await msg.answer(
        "🔗 Kanal @username ini yuboring (masalan: <code>@bekstyle_uz</code>).\n"
        "Avval botni kanalga «Post joylash» huquqi bilan admin qiling.",
        reply_markup=reply_kb(),
    )
    await callback.answer()


@router.message(LinkChannel.username, F.text)
async def on_channel_username(message: Message, state: FSMContext, bot: Bot) -> None:
    match = CHANNEL_RE.fullmatch((message.text or "").strip())
    if match is None or message.from_user is None:
        await message.answer("⚠️ Kanal @username ini yuboring.")
        return
    chat, error = await verify_channel(bot, f"@{match.group(1)}", message.from_user.id)
    if chat is None:
        await message.answer(error)
        return
    await state.clear()
    await message.answer(await _save_channel(chat), reply_markup=await menu_for(message.from_user.id))


@router.callback_query(F.data == "ch:unlink")
async def on_channel_unlink(callback: CallbackQuery) -> None:
    if not await _owner_only(callback):
        return
    async with async_session() as session:
        await set_setting(session, "channel_id", "")
        await set_setting(session, "channel_username", "")
    await show_in(callback, *await settings_view())


# ---------- broadcast ----------
@router.callback_query(F.data == "a:bc")
async def on_broadcast(callback: CallbackQuery, state: FSMContext) -> None:
    msg = cb_message(callback)
    if msg is None:
        return
    await state.set_state(Broadcast.message)
    await msg.answer(
        "📣 Barcha mijozlarga yuboriladigan xabarni yuboring (matn, rasm, video — istalgan).",
        reply_markup=reply_kb(),
    )
    await callback.answer()


@router.message(Broadcast.message)
async def on_broadcast_message(message: Message, state: FSMContext) -> None:
    await state.update_data(from_chat=message.chat.id, message_id=message.message_id)
    await state.set_state(Broadcast.confirm)
    await message.answer(
        "👆 Shu xabar barcha mijozlarga yuboriladi. Tasdiqlaysizmi?",
        reply_markup=inline([("✅ Yuborish", "bc:go"), ("❌ Bekor", "bc:no")]),
    )


@router.callback_query(Broadcast.confirm, F.data == "bc:go")
async def on_broadcast_go(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    data = await state.get_data()
    await state.clear()
    task = asyncio.create_task(
        run_broadcast(bot, int(data["from_chat"]), int(data["message_id"]), callback.from_user.id)
    )
    _background.add(task)
    task.add_done_callback(_background.discard)
    await show_in(callback, "📣 Yuborilmoqda… Tugagach hisobot keladi.")
    msg = cb_message(callback)
    if msg:
        await msg.answer("👇 Menyu", reply_markup=await menu_for(callback.from_user.id))


@router.callback_query(Broadcast.confirm, F.data == "bc:no")
async def on_broadcast_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await show_in(callback, "❌ Xabar yuborilmadi.")
    msg = cb_message(callback)
    if msg:
        await msg.answer("👇 Menyu", reply_markup=await menu_for(callback.from_user.id))
