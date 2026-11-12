"""
Moonlight Chinese Shop - Premium Animated Emojis & Stickers Service.
Provides verified Telegram Premium animated custom emojis (<tg-emoji emoji-id="...">)
and styled inline buttons with icon_custom_emoji_id.
"""

import re
import logging
from typing import Optional, Dict, Any
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

logger = logging.getLogger(__name__)

# Verified Telegram Premium Custom Emojis (Bot API 7.0+)
# Unlocked via bot owner's Telegram Premium subscription
TG_MOON = '<tg-emoji emoji-id="5429099589997184246">🌙</tg-emoji>'
TG_SAKURA = '<tg-emoji emoji-id="5465119341815027379">🌸</tg-emoji>'
TG_PARTY = '<tg-emoji emoji-id="5436040291507247633">🎉</tg-emoji>'
TG_PIN = '<tg-emoji emoji-id="5429270061544130296">📍</tg-emoji>'
TG_USER = '<tg-emoji emoji-id="5373012449597335010">👤</tg-emoji>'
TG_PRODUCT = '<tg-emoji emoji-id="5429587463922272406">👛</tg-emoji>'
TG_STAR = '<tg-emoji emoji-id="5429351167706547656">🌟</tg-emoji>'
TG_MONEY = '<tg-emoji emoji-id="5375296873982604963">💰</tg-emoji>'
TG_CARGO = '<tg-emoji emoji-id="5429388216094444138">🎁</tg-emoji>'
TG_TIME = '<tg-emoji emoji-id="5431807687136395567">⏰</tg-emoji>'
TG_SPARKLE = '<tg-emoji emoji-id="5472164874886846699">✨</tg-emoji>'
TG_FIRE = '<tg-emoji emoji-id="5420315771991497307">🔥</tg-emoji>'
TG_DIAMOND = '<tg-emoji emoji-id="5429153655045507054">💎</tg-emoji>'
TG_CROWN = '<tg-emoji emoji-id="5429387335626145566">👑</tg-emoji>'
TG_RIBBON = '<tg-emoji emoji-id="5429504631183001681">🎀</tg-emoji>'
TG_CART = '<tg-emoji emoji-id="5431499171045581032">🛒</tg-emoji>'
TG_BAGS = '<tg-emoji emoji-id="5373052667671093676">🛍</tg-emoji>'
TG_PLANE = '<tg-emoji emoji-id="5429402517042566710">✈️</tg-emoji>'
TG_AUTO = '<tg-emoji emoji-id="5429440624022464104">🚗</tg-emoji>'
TG_LETTER = '<tg-emoji emoji-id="5429532824707289895">💌</tg-emoji>'
TG_HEART = '<tg-emoji emoji-id="5429388216094444138">💗</tg-emoji>'
TG_CHECK = '<tg-emoji emoji-id="5429351167706547656">✅</tg-emoji>'

# Premium Button Icon ID
PREMIUM_BTN_BAG_ID = "5373052667671093676"  # Shopping bags from RestrictedEmoji
PREMIUM_BTN_STAR_ID = "5429351167706547656"  # Glowing star

# Emoji substitution dictionary for automatic upgrading of any bot post
EMOJI_TO_PREMIUM = {
    "🌙": TG_MOON,
    "🌸": TG_SAKURA,
    "🎉": TG_PARTY,
    "📌": TG_PIN,
    "👤": TG_USER,
    "👗": TG_PRODUCT,
    "💰": TG_MONEY,
    "📦": TG_CARGO,
    "⏳": TG_TIME,
    "⏰": TG_TIME,
    "✨": TG_SPARKLE,
    "🔥": TG_FIRE,
    "💎": TG_DIAMOND,
    "👑": TG_CROWN,
    "🎀": TG_RIBBON,
    "🛒": TG_CART,
    "🛍️": TG_BAGS,
    "🛍": TG_BAGS,
    "✈️": TG_PLANE,
    "🚗": TG_AUTO,
    "🚚": TG_AUTO,
    "💌": TG_LETTER,
    "💗": TG_HEART,
    "✅": TG_CHECK,
    "🔹": TG_STAR,
    "⭐": TG_STAR,
}


def upgrade_to_premium_emojis(text: str) -> str:
    """
    Scans any message text and upgrades standard emojis to verified
    Telegram Premium animated custom emojis.
    Preserves text already wrapped in <tg-emoji>.
    """
    if not text:
        return text

    # Split text into segments: parts inside <tg-emoji>...</tg-emoji> remain untouched,
    # parts outside are transformed.
    pattern = r'(<tg-emoji[^>]*>.*?</tg-emoji>)'
    tokens = re.split(pattern, text)

    transformed_tokens = []
    for token in tokens:
        if token.startswith("<tg-emoji"):
            transformed_tokens.append(token)
        else:
            cur = token
            for char, premium_tag in sorted(EMOJI_TO_PREMIUM.items(), key=lambda x: -len(x[0])):
                cur = cur.replace(char, premium_tag)
            transformed_tokens.append(cur)

    return "".join(transformed_tokens)


def strip_custom_emojis(text: str) -> str:
    """Fallback utility: removes <tg-emoji> wrappers, leaving fallback regular emojis."""
    return re.sub(r'<tg-emoji emoji-id="[^"]*">([^<]+)</tg-emoji>', r'\1', text)


def make_premium_button(
    text: str,
    url: Optional[str] = None,
    callback_data: Optional[str] = None,
    web_app: Optional[Any] = None,
    icon_id: str = PREMIUM_BTN_BAG_ID,
    style: str = "primary",
) -> InlineKeyboardButton:
    """
    Creates an InlineKeyboardButton enhanced with Telegram Premium animated icon and styling.
    """
    clean_text = text
    # Strip leading emoji if it matches standard emojis so icon_custom_emoji_id takes pride of place
    for emoji_prefix in ["🛍️", "🛍", "🌸", "✨", "🎀", "👗", "⭐"]:
        if clean_text.startswith(emoji_prefix):
            clean_text = clean_text[len(emoji_prefix):].strip()
            break

    kwargs: Dict[str, Any] = {
        "text": clean_text,
        "icon_custom_emoji_id": icon_id,
        "style": style,
    }
    if url:
        kwargs["url"] = url
    if callback_data:
        kwargs["callback_data"] = callback_data
    if web_app:
        kwargs["web_app"] = web_app

    return InlineKeyboardButton(**kwargs)


def fallback_button(
    text: str,
    url: Optional[str] = None,
    callback_data: Optional[str] = None,
    web_app: Optional[Any] = None,
    fallback_prefix: str = "🛍️ ",
) -> InlineKeyboardButton:
    """Creates a standard fallback InlineKeyboardButton without custom emoji attributes."""
    btn_text = text if any(text.startswith(e) for e in ["🛍️", "🛍", "🌸", "✨"]) else f"{fallback_prefix}{text}"
    kwargs: Dict[str, Any] = {"text": btn_text}
    if url:
        kwargs["url"] = url
    if callback_data:
        kwargs["callback_data"] = callback_data
    if web_app:
        kwargs["web_app"] = web_app
    return InlineKeyboardButton(**kwargs)


async def send_premium_message(
    bot_instance: Any,
    chat_id: Any,
    text: str,
    reply_markup: Optional[InlineKeyboardMarkup] = None,
    parse_mode: str = "HTML",
    **kwargs: Any,
) -> Any:
    """
    Safely sends a message enhanced with Telegram Premium custom emojis.
    If the receiving chat or Telegram client rejects custom emojis,
    automatically falls back to standard text and buttons with zero failure.
    """
    upgraded_text = upgrade_to_premium_emojis(text)
    try:
        return await bot_instance.send_message(
            chat_id=chat_id,
            text=upgraded_text,
            reply_markup=reply_markup,
            parse_mode=parse_mode,
            **kwargs,
        )
    except Exception as e:
        logger.warning(f"send_premium_message failed with custom emojis ({e}); trying fallback...")
        fallback_text = strip_custom_emojis(text)
        return await bot_instance.send_message(
            chat_id=chat_id,
            text=fallback_text,
            reply_markup=reply_markup,
            parse_mode=parse_mode,
            **kwargs,
        )
