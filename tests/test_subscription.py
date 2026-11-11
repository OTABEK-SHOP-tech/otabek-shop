import pytest
from unittest.mock import AsyncMock, MagicMock
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import InlineKeyboardMarkup
from sqlalchemy import select

from bot.services.subscription import (
    check_single_membership,
    check_dual_subscription,
    is_user_admin,
    get_subscription_targets,
    get_subscription_markup,
    DEFAULT_CHANNEL_ID,
    DEFAULT_CHANNEL_URL,
    DEFAULT_CHAT_ID,
    DEFAULT_CHAT_URL,
)
from db.models import Admin, Setting


@pytest.mark.asyncio
async def test_get_subscription_targets_defaults(test_db_session):
    async with test_db_session() as session:
        targets = await get_subscription_targets(session)
        assert targets["channel_id"] == DEFAULT_CHANNEL_ID
        assert targets["channel_url"] == DEFAULT_CHANNEL_URL
        assert targets["chat_id"] == DEFAULT_CHAT_ID
        assert targets["chat_url"] == DEFAULT_CHAT_URL


@pytest.mark.asyncio
async def test_get_subscription_targets_from_db(test_db_session):
    async with test_db_session() as session:
        for k, v in [
            ("channel_id", "-100999"),
            ("channel_url", "https://t.me/custom_channel"),
            ("chat_id", "-100888"),
            ("chat_url", "https://t.me/custom_chat"),
        ]:
            row = (await session.execute(select(Setting).where(Setting.key == k))).scalars().first()
            if row:
                row.value = v
            else:
                session.add(Setting(key=k, value=v))
        await session.commit()

        targets = await get_subscription_targets(session)
        assert targets["channel_id"] == "-100999"
        assert targets["channel_url"] == "https://t.me/custom_channel"
        assert targets["chat_id"] == "-100888"
        assert targets["chat_url"] == "https://t.me/custom_chat"


@pytest.mark.asyncio
async def test_is_user_admin(test_db_session):
    async with test_db_session() as session:
        session.add(Admin(telegram_id=999888, name="Test Owner", role="owner"))
        await session.commit()

        assert await is_user_admin(session, 999888) is True
        assert await is_user_admin(session, 111222) is False


@pytest.mark.asyncio
async def test_check_single_membership_statuses():
    bot = MagicMock()

    # 1. Active member
    bot.get_chat_member = AsyncMock(return_value=MagicMock(status="member"))
    assert await check_single_membership(bot, "-1001", 123) is True

    # 2. Administrator
    bot.get_chat_member = AsyncMock(return_value=MagicMock(status="administrator"))
    assert await check_single_membership(bot, "-1001", 123) is True

    # 3. Creator
    bot.get_chat_member = AsyncMock(return_value=MagicMock(status="creator"))
    assert await check_single_membership(bot, "-1001", 123) is True

    # 4. Left / Kicked
    bot.get_chat_member = AsyncMock(return_value=MagicMock(status="left"))
    assert await check_single_membership(bot, "-1001", 123) is False

    bot.get_chat_member = AsyncMock(return_value=MagicMock(status="kicked"))
    assert await check_single_membership(bot, "-1001", 123) is False

    # 5. TelegramBadRequest with participant invalid
    bot.get_chat_member = AsyncMock(
        side_effect=TelegramBadRequest(method=MagicMock(), message="Bad Request: PARTICIPANT_ID_INVALID")
    )
    assert await check_single_membership(bot, "-1001", 123) is False


@pytest.mark.asyncio
async def test_check_dual_subscription(test_db_session):
    bot = MagicMock()

    async def mock_get_chat_member(chat_id, user_id):
        if str(chat_id) == DEFAULT_CHANNEL_ID:
            return MagicMock(status="member")
        if str(chat_id) == DEFAULT_CHAT_ID:
            return MagicMock(status="left")
        return MagicMock(status="left")

    bot.get_chat_member = AsyncMock(side_effect=mock_get_chat_member)

    async with test_db_session() as session:
        is_ch, is_chat, ch_url, chat_url = await check_dual_subscription(bot, session, 555)
        assert is_ch is True
        assert is_chat is False
        assert ch_url == DEFAULT_CHANNEL_URL
        assert chat_url == DEFAULT_CHAT_URL


def test_subscription_markup():
    markup = get_subscription_markup("https://t.me/channel", "https://t.me/chat")
    assert isinstance(markup, InlineKeyboardMarkup)
    assert len(markup.inline_keyboard) == 3
    assert markup.inline_keyboard[0][0].url == "https://t.me/channel"
    assert markup.inline_keyboard[1][0].url == "https://t.me/chat"
    assert markup.inline_keyboard[2][0].callback_data == "check_subscription"
