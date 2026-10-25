from aiogram.filters import BaseFilter
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardMarkup,
    Message,
    ReplyKeyboardMarkup,
)

from bekstyle.db import async_session
from bekstyle.keyboards import main_menu
from bekstyle.notify import safe_edit_text
from bekstyle.services import is_admin


async def menu_for(user_id: int) -> ReplyKeyboardMarkup:
    async with async_session() as session:
        return main_menu(await is_admin(session, user_id))


class IsAdmin(BaseFilter):
    async def __call__(self, event: Message | CallbackQuery) -> bool:
        if event.from_user is None:
            return False
        async with async_session() as session:
            return await is_admin(session, event.from_user.id)


def cb_message(callback: CallbackQuery) -> Message | None:
    """The callback's message, or None when Telegram no longer lets us touch it (older than 48h)."""
    return callback.message if isinstance(callback.message, Message) else None


def cb_int(callback: CallbackQuery, index: int) -> int:
    return int((callback.data or "").split(":")[index])


async def show_in(
    callback: CallbackQuery,
    text: str,
    markup: InlineKeyboardMarkup | None = None,
    alert: str | None = None,
) -> None:
    """Edit the callback's text message in place; photo or stale messages get a fresh message instead."""
    msg = cb_message(callback)
    if msg and msg.text:
        await safe_edit_text(msg, text, markup)
    elif msg:
        await msg.answer(text, reply_markup=markup)
    await callback.answer(alert, show_alert=alert is not None)
