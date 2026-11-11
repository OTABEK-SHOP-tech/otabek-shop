"""
Mandatory Channel and Chat subscription service for Moonlight Chinese Shop bot.

Users must be members of BOTH:
1. Official Channel (@moonlight_chinese_shop)
2. Official Chat / Group (@MY_interesno)

Admins and owners are exempt from this requirement.
"""
import asyncio
import logging
from typing import Optional, Tuple, Dict, Any

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Admin, Setting

logger = logging.getLogger(__name__)

# Default verified channel and chat targets
DEFAULT_CHANNEL_ID = "-1004378811161"
DEFAULT_CHANNEL_URL = "https://t.me/moonlight_chinese_shop"
DEFAULT_CHAT_ID = "-1003565030513"
DEFAULT_CHAT_URL = "https://t.me/MY_interesno"


async def get_subscription_targets(session: AsyncSession) -> Dict[str, str]:
    """Retrieves target channel and chat configurations from settings with defaults."""
    res_ch_id = await session.execute(select(Setting).where(Setting.key == "channel_id"))
    ch_id_row = res_ch_id.scalars().first()
    channel_id = ch_id_row.value.strip() if (ch_id_row and ch_id_row.value.strip()) else DEFAULT_CHANNEL_ID

    res_ch_url = await session.execute(select(Setting).where(Setting.key == "channel_url"))
    ch_url_row = res_ch_url.scalars().first()
    channel_url = ch_url_row.value.strip() if (ch_url_row and ch_url_row.value.strip()) else DEFAULT_CHANNEL_URL

    res_chat_id = await session.execute(select(Setting).where(Setting.key == "chat_id"))
    chat_id_row = res_chat_id.scalars().first()
    chat_id = chat_id_row.value.strip() if (chat_id_row and chat_id_row.value.strip()) else DEFAULT_CHAT_ID

    res_chat_url = await session.execute(select(Setting).where(Setting.key == "chat_url"))
    chat_url_row = res_chat_url.scalars().first()
    chat_url = chat_url_row.value.strip() if (chat_url_row and chat_url_row.value.strip()) else DEFAULT_CHAT_URL

    return {
        "channel_id": channel_id,
        "channel_url": channel_url,
        "chat_id": chat_id,
        "chat_url": chat_url,
    }


async def is_user_admin(session: AsyncSession, user_id: int) -> bool:
    """Check if user is an admin or owner (exempt from forced subscription)."""
    res = await session.execute(
        select(Admin).where(Admin.telegram_id == user_id)
    )
    return res.scalars().first() is not None


async def check_single_membership(bot: Bot, chat_target: str, user_id: int) -> bool:
    """
    Checks if user is an active member in the specified chat/channel.
    Returns:
      True: user is member/admin/creator
      False: user is not member or has left/been kicked
    """
    try:
        # Convert numeric strings like "-1004378811161" to int
        try:
            target_id = int(chat_target)
        except (ValueError, TypeError):
            target_id = chat_target

        member = await bot.get_chat_member(chat_id=target_id, user_id=user_id)
        status = member.status

        if status in ("creator", "administrator", "member"):
            return True
        elif status == "restricted":
            return bool(getattr(member, "is_member", True))
        elif status in ("left", "kicked"):
            return False
        return False
    except TelegramBadRequest as e:
        msg = str(e).lower()
        if any(term in msg for term in ("participant_id_invalid", "user not found", "not participant", "chat not found")):
            return False
        logger.warning(f"TelegramBadRequest checking membership for {user_id} in {chat_target}: {e}")
        return True
    except TelegramForbiddenError as e:
        logger.error(f"Bot has no access to chat {chat_target}: {e}")
        return True
    except Exception as e:
        logger.warning(f"Unexpected error checking membership for {user_id} in {chat_target}: {e}")
        return True


async def check_dual_subscription(
    bot: Bot, session: AsyncSession, user_id: int
) -> Tuple[bool, bool, str, str]:
    """
    Checks membership in both channel and chat.
    Returns: (is_channel_sub, is_chat_sub, channel_url, chat_url)
    """
    targets = await get_subscription_targets(session)

    ch_task = check_single_membership(bot, targets["channel_id"], user_id)
    chat_task = check_single_membership(bot, targets["chat_id"], user_id)

    is_channel_sub, is_chat_sub = await asyncio.gather(ch_task, chat_task)

    return is_channel_sub, is_chat_sub, targets["channel_url"], targets["chat_url"]


def get_subscription_markup(channel_url: str, chat_url: str) -> InlineKeyboardMarkup:
    """Builds inline keyboard prompting user to join both channel and chat."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📢 1. Rasmiy kanalga a'zo bo'lish", url=channel_url)],
            [InlineKeyboardButton(text="💬 2. Rasmiy guruhga qo'shilish", url=chat_url)],
            [InlineKeyboardButton(text="✅ A'zo bo'ldim (Obunani tekshirish)", callback_data="check_subscription")],
        ]
    )


SUBSCRIBE_PROMPT_TEXT = (
    "🌙 <b>Moonlight Chinese Shop ga xush kelibsiz!</b> ✨\n\n"
    "Botdan to'liq foydalanish va nozik mahsulotlarimizni Mini App orqali xarid qilish uchun "
    "rasmiy kanalimiz va muloqot guruhimizga a'zo bo'ling:\n\n"
    "📢 <b>1. Rasmiy kanal:</b> Yangi kolleksiyalar va maxsus chegirmalar\n"
    "💬 <b>2. Rasmiy guruh:</b> Mijozlar bilan jonli fikrlar va savol-javoblar\n\n"
    "Ikkalasiga ham a'zo bo'lgach, pastdagi <b>✅ A'zo bo'ldim</b> tugmasini bosing! 🛍️"
)
