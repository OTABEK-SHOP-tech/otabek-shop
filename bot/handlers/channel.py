from html import escape
import logging
import re
from typing import Tuple

from aiogram import Bot, Router, F
from aiogram.enums import ChatMemberStatus
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import ChatMemberUpdated, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import settings
from bot.loader import bot
from bot.services.contest_service import get_active_contest
from db.models import Admin, Contest, Setting
from db.session import async_session_factory

router = Router(name="channel")
router.message.filter(F.chat.type == "private")
logger = logging.getLogger(__name__)

CHANNEL_REF_RE = re.compile(r"(?:https?://)?(?:t\.me/|@)?([A-Za-z0-9_]{5,32})/?")


class ChannelLinkState(StatesGroup):
    waiting_for_username = State()


async def is_shop_owner(session: AsyncSession, user_id: int) -> bool:
    if settings.DEV_ADMIN_ID and user_id == settings.DEV_ADMIN_ID:
        return True
    res = await session.execute(select(Admin).where(Admin.telegram_id == user_id))
    admin = res.scalars().first()
    return admin is not None and admin.role == "owner"


async def save_channel_id(session: AsyncSession, chat_id: str) -> None:
    res_ch = await session.execute(select(Setting).where(Setting.key == "channel_id"))
    ch_setting = res_ch.scalars().first()
    if ch_setting:
        ch_setting.value = chat_id
    else:
        session.add(Setting(key="channel_id", value=chat_id))
    await session.commit()


async def link_channel_by_username(session: AsyncSession, tg_bot: Bot, user_id: int, raw: str) -> Tuple[bool, str]:
    """Links a channel where the bot can post and user_id is an admin. Returns (linked, reply text)."""
    m = CHANNEL_REF_RE.fullmatch(raw.strip())
    if not m:
        return False, "❌ Kanal @username ini yuboring (masalan: <code>@moonlight_chinese_shop</code>) yoki /cancel."
    ref = f"@{m.group(1)}"
    try:
        chat = await tg_bot.get_chat(ref)
        me = await tg_bot.get_me()
        bot_member = await tg_bot.get_chat_member(chat_id=chat.id, user_id=me.id)
        user_member = await tg_bot.get_chat_member(chat_id=chat.id, user_id=user_id)
    except Exception as e:
        logger.warning(f"Channel link lookup failed for {ref}: {e}")
        return False, f"❌ {escape(ref)} topilmadi yoki bot u yerda yo'q. Botni kanalga admin qilib, qayta yuboring."

    if chat.type != "channel":
        return False, "❌ Bu kanal emas. Faqat Telegram kanallarni ulash mumkin (guruhlarni emas)."
    if bot_member.status != ChatMemberStatus.ADMINISTRATOR or (
        chat.type == "channel" and not getattr(bot_member, "can_post_messages", False)
    ):
        return False, "❌ Bot bu kanalda post joylash huquqi bilan admin emas."
    if user_member.status not in (ChatMemberStatus.CREATOR, ChatMemberStatus.ADMINISTRATOR):
        return False, "❌ Siz bu kanalda admin emassiz."

    await save_channel_id(session, str(chat.id))
    return True, f"✅ <b>Kanal ulandi:</b> {escape(str(chat.title))} (<code>{chat.id}</code>) 🌸"


async def unlink_channel(session: AsyncSession) -> Tuple[bool, str]:
    # Unlinking mid-contest would make every invitee's ✅ Tasdiqlash fail.
    if await get_active_contest(session):
        return False, "⛔ Faol konkurs bor. Avval konkursni tugating yoki bekor qiling, keyin kanalni uzing."
    await save_channel_id(session, "")
    return True, "📢 Kanal uzildi. Qayta ulash: ⚙️ Sozlamalar → 🔗 Kanalni ulash."


@router.my_chat_member()
async def handle_bot_chat_member_update(event: ChatMemberUpdated):
    """
    Detects when the bot is added as administrator to a channel, or removed.
    """
    chat = event.chat
    # Only broadcast channels can be linked as channel_id!
    # Groups/supergroups are discussion chats (chat_id), never channel_id.
    if chat.type != "channel":
        if chat.type in ["group", "supergroup"] and event.new_chat_member.status == ChatMemberStatus.ADMINISTRATOR:
            async with async_session_factory() as session:
                actor_id = event.from_user.id if event.from_user else 0
                if not actor_id or not await is_shop_owner(session, actor_id):
                    logger.warning(
                        f"Bot added to group {escape(str(chat.title))} ({chat.id}) by non-owner {actor_id}. Ignored."
                    )
                    return
                logger.info(f"Bot added to discussion group {chat.title} ({chat.id}) by owner {actor_id}. Updating chat_id.")
                res_chat = await session.execute(select(Setting).where(Setting.key == "chat_id"))
                s = res_chat.scalars().first()
                if s:
                    s.value = str(chat.id)
                else:
                    session.add(Setting(key="chat_id", value=str(chat.id)))
                await session.commit()
        return

    from_user = event.from_user
    old_status = event.old_chat_member.status
    new_status = event.new_chat_member.status

    async with async_session_factory() as session:
        # Get owners
        res_owners = await session.execute(select(Admin).where(Admin.role == "owner"))
        owners = res_owners.scalars().all()
        owner_ids = [o.telegram_id for o in owners]
        if not owner_ids and settings.DEV_ADMIN_ID:
            owner_ids = [settings.DEV_ADMIN_ID]

        # Case 1: Bot added as Administrator
        if new_status == ChatMemberStatus.ADMINISTRATOR and getattr(event.new_chat_member, "can_post_messages", True):
            # Accept channels added by any verified shop owner, not only the first one in the table
            if not from_user or not await is_shop_owner(session, from_user.id):
                actor_id = from_user.id if from_user else 0
                logger.warning(
                    f"Bot added to channel {escape(str(chat.title))} ({chat.id}) by non-owner {actor_id}. Ignored."
                )
                return

            markup = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="✅ Ha, ulash / Link",
                            callback_data=f"confirm_link_channel_{chat.id}"
                        ),
                        InlineKeyboardButton(
                            text="❌ Yo'q / Cancel",
                            callback_data="cancel_link_channel"
                        )
                    ]
                ]
            )

            try:
                await bot.send_message(
                    chat_id=from_user.id,
                    text=(
                        f"🌸 <b>Yangi kanal aniqlandi:</b>\n"
                        f"📢 <b>Nomi:</b> {escape(str(chat.title))}\n"
                        f"🔗 <b>Username:</b> @{chat.username or 'mavjud emas'}\n"
                        f"🆔 <b>ID:</b> <code>{chat.id}</code>\n\n"
                        f"Ushbu kanalni do'konga ulaymi? / Link this channel?"
                    ),
                    reply_markup=markup,
                )
            except Exception as e:
                logger.error(f"Could not send DM to owner {from_user.id}: {e}")

        # Case 2: Bot removed or kicked
        elif new_status in [ChatMemberStatus.LEFT, ChatMemberStatus.KICKED]:
            res_ch = await session.execute(select(Setting).where(Setting.key == "channel_id"))
            ch_setting = res_ch.scalars().first()
            if ch_setting and ch_setting.value == str(chat.id):
                ch_setting.value = ""
                res_c = await session.execute(select(Contest).where(Contest.status == "active"))
                active_c = res_c.scalars().first()
                if active_c:
                    active_c.status = "paused"
                await session.commit()

                for oid in owner_ids:
                    try:
                        await bot.send_message(
                            chat_id=oid,
                            text=(
                                f"⚠️ <b>Bot '{escape(str(chat.title))}' kanalidan chiqarildi.</b>\n"
                                f"Kanal do'kondan avtomatik tarzda uzildi."
                            )
                        )
                    except Exception:
                        pass

        # Case 3: Bot demoted or lost post rights in the linked channel
        elif old_status in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR) and (
            new_status not in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR)
            or not getattr(event.new_chat_member, "can_post_messages", True)
        ):
            res_ch = await session.execute(select(Setting).where(Setting.key == "channel_id"))
            ch_setting = res_ch.scalars().first()
            if ch_setting and ch_setting.value == str(chat.id):
                logger.warning(f"Bot demoted or lost posting rights in linked channel {chat.id}. Pausing active contest.")
                res_c = await session.execute(select(Contest).where(Contest.status == "active"))
                active_c = res_c.scalars().first()
                if active_c:
                    active_c.status = "paused"
                    await session.commit()

                for oid in owner_ids:
                    try:
                        await bot.send_message(
                            chat_id=oid,
                            text=(
                                "🚨 <b>DIQQAT! Bot kanalda admin huquqidan mahrum bo'ldi!</b>\n\n"
                                "Konkurs hisob-kitobida xatolik bo'lmasligi uchun konkurs vaqtincha to'xtatildi (Pauza).\n"
                                "Iltimos, botni qaytadan kanalga to'liq admin qilib qo'ying."
                            )
                        )
                    except Exception:
                        pass


@router.callback_query(F.data.startswith("confirm_link_channel_"))
async def handle_confirm_link_channel(callback: CallbackQuery):
    chat_id = callback.data.replace("confirm_link_channel_", "").strip()
    user_id = callback.from_user.id

    async with async_session_factory() as session:
        if not await is_shop_owner(session, user_id):
            await callback.answer("⛔ Faqat do'kon egasi kanalni ulashi mumkin!", show_alert=True)
            return
        await save_channel_id(session, chat_id)

    await callback.message.edit_text(
        f"✅ <b>Kanal muvaffaqiyatli ulandi!</b> 🌸\n"
        f"Kanal ID: <code>{chat_id}</code>\n\n"
        f"Endi har safar yangi mahsulot qo'shganingizda uni bir bosishda kanalingizga joylashingiz mumkin!"
    )
    await callback.answer("✅ Kanal ulandi!")


@router.callback_query(F.data == "cancel_link_channel")
async def handle_cancel_link_channel(callback: CallbackQuery):
    await callback.message.edit_text("❌ Kanal ulanmadi.")
    await callback.answer("Bekor qilindi.")


# Manual linking for when the bot was made admin by someone who isn't a shop owner in the bot.
@router.callback_query(F.data == "admin_link_channel")
async def handle_link_channel_prompt(callback: CallbackQuery, state: FSMContext):
    async with async_session_factory() as session:
        if not await is_shop_owner(session, callback.from_user.id):
            await callback.answer("⛔ Faqat do'kon egasi kanalni ulashi mumkin!", show_alert=True)
            return
    await state.set_state(ChannelLinkState.waiting_for_username)
    await callback.message.answer(
        "🔗 <b>Kanalni ulash</b>\n\n"
        "Kanal @username ini yuboring (masalan: <code>@moonlight_chinese_shop</code>).\n"
        "Bot kanalda post joylash huquqi bilan admin bo'lishi, siz esa kanal admini bo'lishingiz kerak.\n\n"
        "Bekor qilish: /cancel"
    )
    await callback.answer()


@router.message(ChannelLinkState.waiting_for_username)
async def process_link_channel(message: Message, state: FSMContext):
    text_val = (message.text or "").strip()
    if text_val.lower() == "/cancel":
        await state.clear()
        await message.answer("❌ Kanal ulanmadi.")
        return
    async with async_session_factory() as session:
        linked, reply = await link_channel_by_username(session, message.bot, message.from_user.id, text_val)
    if linked:
        await state.clear()
    await message.answer(reply)


@router.callback_query(F.data == "admin_unlink_channel")
async def handle_unlink_channel(callback: CallbackQuery):
    async with async_session_factory() as session:
        if not await is_shop_owner(session, callback.from_user.id):
            await callback.answer("⛔ Faqat do'kon egasi kanalni uzishi mumkin!", show_alert=True)
            return
        _, reply = await unlink_channel(session)
    await callback.answer(reply, show_alert=True)
