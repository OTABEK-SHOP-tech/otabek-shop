import os
import logging
from typing import Dict, Any, List
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto, FSInputFile
from pathlib import Path
from sqlalchemy import select

from api.config import settings
from api.services.formatters import build_channel_caption
from api.services.telegram_fetcher import get_absolute_media_dir
from bot.loader import bot
from bot.services.premium_emojis import upgrade_to_premium_emojis, strip_custom_emojis, make_premium_button, fallback_button
from db.models import Product, Setting
from db.session import async_session_factory

logger = logging.getLogger(__name__)


async def post_product_to_channel(product: Product) -> Dict[str, Any]:
    if not bot:
        return {"success": False, "error": "Bot is not running"}

    async with async_session_factory() as session:
        # Get channel settings
        res_ch = await session.execute(select(Setting).where(Setting.key == "channel_id"))
        ch_setting = res_ch.scalars().first()
        channel_id = (ch_setting.value or "").strip() if ch_setting else ""

        # Default to official Moonlight channel if not configured
        if not channel_id:
            channel_id = "@moonlight_chinese_shop"

        # Get delivery terms & contact
        res_settings = await session.execute(select(Setting))
        settings_map = {s.key: s.value for s in res_settings.scalars().all()}

        cargo_rate = int(settings_map.get("cargo_rate", 12000))
        delivery_days = settings_map.get("delivery_days", "10–15 kun ichida")
        delivery_scope = settings_map.get("delivery_scope", "O'zbekiston bo'ylab")
        contact_username = settings_map.get("contact_username", "MOONLIGHT_ADMINNN")
        reviews_channel = settings_map.get("reviews_channel", "moonlight_shop_otzv")

        raw_caption = build_channel_caption(
            category_slug=product.category,
            price=product.price,
            cargo_rate=cargo_rate,
            delivery_days=delivery_days,
            delivery_scope=delivery_scope,
            contact_username=contact_username,
            title=product.title,
            sizes=product.sizes or [],
            reviews_channel=reviews_channel,
            cargo_separate=True,
            adapted_style=True,
        )
        premium_caption = upgrade_to_premium_emojis(raw_caption)

        # Get bot username for deep link
        try:
            bot_info = await bot.get_me()
            bot_username = bot_info.username or "moonlight_shop_bot"
        except Exception:
            bot_username = "moonlight_shop_bot"
        product_webapp_url = f"https://t.me/{bot_username}?startapp=product_{product.id}"

        media_dir = get_absolute_media_dir()
        photos = product.photos or []

        def _get_media_input(photo_id: str):
            if not photo_id:
                return None
            local_file = media_dir / photo_id
            if local_file.is_file():
                return FSInputFile(str(local_file))
            # Direct file_id or web URL
            return photo_id

        async def _attempt_post(use_premium: bool) -> int:
            cap = premium_caption if use_premium else strip_custom_emojis(raw_caption)
            btn = (
                make_premium_button(
                    text="🛍️ Do'konda ko'rish",
                    url=product_webapp_url,
                    icon_id="5373052667671093676",
                    style="primary",
                )
                if use_premium
                else fallback_button(
                    text="🛍️ Do'konda ko'rish",
                    url=product_webapp_url,
                )
            )
            reply_markup = InlineKeyboardMarkup(inline_keyboard=[[btn]])

            if photos and len(photos) > 1:
                # Media album
                media_group: List[InputMediaPhoto] = []
                for idx, photo_id in enumerate(photos[:10]):
                    m_obj = _get_media_input(photo_id)
                    media_group.append(
                        InputMediaPhoto(
                            media=m_obj,
                            caption=cap if idx == 0 else None,
                        )
                    )
                messages = await bot.send_media_group(chat_id=channel_id, media=media_group)
                sent_id = messages[0].message_id
                # Send follow-up button
                await bot.send_message(
                    chat_id=channel_id,
                    text="🌸 Mahsulotni Mini App orqali tomosha qilish va savatga qo'shish:",
                    reply_markup=reply_markup,
                )
                return sent_id
            elif photos and len(photos) == 1:
                photo_obj = _get_media_input(photos[0])
                msg = await bot.send_photo(
                    chat_id=channel_id,
                    photo=photo_obj,
                    caption=cap,
                    reply_markup=reply_markup,
                )
                return msg.message_id
            else:
                msg = await bot.send_message(
                    chat_id=channel_id,
                    text=cap,
                    reply_markup=reply_markup,
                )
                return msg.message_id

        try:
            sent_msg_id = None
            try:
                sent_msg_id = await _attempt_post(use_premium=True)
            except Exception as e_premium:
                logger.warning(
                    f"Posting to channel with custom premium emojis/buttons failed ({e_premium}), "
                    f"retrying with standard emojis and fallback buttons..."
                )
                sent_msg_id = await _attempt_post(use_premium=False)

            # Save message ID
            p_res = await session.execute(select(Product).where(Product.id == product.id))
            p_obj = p_res.scalars().first()
            if p_obj and sent_msg_id:
                p_obj.channel_message_id = sent_msg_id
                await session.commit()

            return {"success": True, "channel_message_id": sent_msg_id}

        except Exception as e:
            logger.error(f"Failed to post product #{product.id} to channel: {e}")
            return {"success": False, "error": str(e)}
