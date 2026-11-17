import logging
from typing import Optional
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage
from api.config import settings

logger = logging.getLogger(__name__)

# Initialize bot and dispatcher
bot: Optional[Bot] = None
dp: Optional[Dispatcher] = None

try:
    raw_token = (settings.BOT_TOKEN or "").strip()
    if raw_token and raw_token != "mock_bot_token_for_tests":
        bot = Bot(
            token=raw_token,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        )
        dp = Dispatcher(storage=MemoryStorage())
    else:
        logger.warning("Bot token not configured or mock token used. Running bot in dry/test mode.")
except Exception as e:
    logger.error(f"Error initializing bot: {e}")
