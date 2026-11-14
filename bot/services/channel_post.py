import os
import logging
from typing import Dict, Any, List
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto, FSInputFile, LinkPreviewOptions
from pathlib import Path
from sqlalchemy import select

from api.config import settings
from api.services.formatters import build_channel_caption, strip_private_pricing_data
from api.services.telegram_fetcher import get_absolute_media_dir
from api.services.vision_ocr import is_phone_screenshot
from bot.loader import bot
from bot.services.premium_emojis import upgrade_to_premium_emojis, strip_custom_emojis, make_premium_button, fallback_button
from db.models import Product, Setting
from db.session import async_session_factory

logger = logging.getLogger(__name__)


async def post_product_to_channel(product: Product) -> Dict[str, Any]:
    if not bot:
        return {"success": False, "error": "Bot is not running"}

    # Hard requirement: NEVER post a product to channel without photos!
    photos = list(product.photos or [])
    if not photos:
        logger.warning(f"Product #{product.id} has no photos, aborting channel post")
        return {"success": False, "error": "Mahsulot rasmi yo'q. Kanalga rasmsiz tovar chiqarilmaydi."}

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

        cargo_rate = int(settings_map.get("cargo_rate", 10000))
        cargo_rate_avia = int(settings_map.get("cargo_rate_avia", 14000))
        cargo_rate_avto = int(settings_map.get("cargo_rate_avto", 10000))
        delivery_days_avia = settings_map.get("delivery_days_avia", "7–9 kun")
        delivery_days_avto = settings_map.get("delivery_days_avto", "14–18 kun")
        delivery_days = settings_map.get("delivery_days", "7–18 kun")
        delivery_scope = settings_map.get("delivery_scope", "O'zbekiston bo'ylab")
        contact_username = settings_map.get("contact_username", "MOONLIGHT_ADMINNN")
        reviews_channel = settings_map.get("reviews_channel", "moonlight_shop_otzv")

        # Get bot username for deep link
        try:
            bot_info = await bot.get_me()
            bot_username = bot_info.username or "moonlight_shop_bot"
        except Exception:
            bot_username = "moonlight_shop_bot"
        clean_bot_username = bot_username.lstrip("@")

        # Telegram Mini App deep links (?startapp=) require BotFather shortname and HTTPS;
        # otherwise Telegram pops up "Invalid". The standard Telegram bot deep link /start product_{id}
        # triggers start.py's product viewer cleanly without any error across all clients!
        if settings.WEBAPP_URL and settings.WEBAPP_URL.startswith("https://"):
            product_webapp_url = f"https://t.me/{clean_bot_username}?startapp=product_{product.id}"
        else:
            product_webapp_url = f"https://t.me/{clean_bot_username}?start=product_{product.id}"

        # Ensure product title is sanitized so private pricing/profit margin never leaks
        clean_product_title = strip_private_pricing_data(product.title) if product.title else None

        media_dir = get_absolute_media_dir()

        # Filter out any phone/spec screenshots from customer-facing channel post
        if photos and len(photos) > 1:
            clean_channel_photos = []
            for p_id in photos:
                img_bytes = None
                p_ref = p_id.file_id if hasattr(p_id, "file_id") else p_id
                if isinstance(p_ref, bytes):
                    img_bytes = p_ref
                elif isinstance(p_ref, str):
                    local_f = media_dir / p_ref
                    if local_f.is_file():
                        try:
                            img_bytes = local_f.read_bytes()
                        except Exception:
                            pass
                    elif bot:
                        try:
                            dl = await bot.download(p_ref)
                            if dl:
                                if hasattr(dl, "read"):
                                    if hasattr(dl, "seek"):
                                        dl.seek(0)
                                    img_bytes = dl.read()
                                elif hasattr(dl, "getvalue"):
                                    img_bytes = dl.getvalue()
                        except Exception:
                            pass

                is_screenshot = False
                if img_bytes and is_phone_screenshot(img_bytes):
                    is_screenshot = True
                elif isinstance(p_ref, str) and any(kw in p_ref.lower() for kw in ("spec", "screenshot", "skrinshot")):
                    is_screenshot = True

                if is_screenshot:
                    continue
                clean_channel_photos.append(p_id)

            if clean_channel_photos and len(clean_channel_photos) < len(photos):
                logger.info(
                    f"Omitted {len(photos) - len(clean_channel_photos)} spec screenshot(s) from channel post for #{product.id}"
                )
                photos = clean_channel_photos

        if not photos:
            return {"success": False, "error": "Mahsulot rasmi yo'q. Kanalga rasmsiz tovar chiqarilmaydi."}

        has_multiple_photos = len(photos) > 1

        raw_caption = build_channel_caption(
            category_slug=product.category,
            price=product.price,
            cargo_rate=cargo_rate,
            cargo_rate_avia=cargo_rate_avia,
            cargo_rate_avto=cargo_rate_avto,
            delivery_days=delivery_days,
            delivery_days_avia=delivery_days_avia,
            delivery_days_avto=delivery_days_avto,
            delivery_scope=delivery_scope,
            contact_username=contact_username,
            title=clean_product_title,
            sizes=product.sizes or [],
            colors=product.colors or [],
            reviews_channel=reviews_channel,
            cargo_separate=True,
            adapted_style=True,
            # For multiple photos (album), we provide webapp_url in caption so customers can click
            # "🛍️ Do'konda xarid qilish" directly inside the album caption without extra messages.
            # For single photo, webapp_url in caption is omitted (None) because the prominent inline button
            # is attached directly underneath the single photo.
            webapp_url=product_webapp_url if has_multiple_photos else None,
        )
        # Defense-in-depth safety check: strip any private pricing tags from final channel post
        raw_caption = strip_private_pricing_data(raw_caption)
        premium_caption = upgrade_to_premium_emojis(raw_caption)

        def _get_media_input(photo_item: Any):
            if not photo_item:
                return None
            p_str = photo_item.file_id if hasattr(photo_item, "file_id") else str(photo_item)
            if os.path.isfile(p_str):
                return FSInputFile(p_str)
            local_file = media_dir / p_str
            if local_file.is_file():
                return FSInputFile(str(local_file))
            # Direct file_id or web URL
            return p_str

        async def _attempt_post(use_premium: bool) -> int:
            cap = premium_caption if use_premium else strip_custom_emojis(raw_caption)
            btn = (
                make_premium_button(
                    text="🛍️ Do'konda xarid qilish",
                    url=product_webapp_url,
                    icon_id="5373052667671093676",
                    style="primary",
                )
                if use_premium
                else fallback_button(
                    text="🛍️ Do'konda xarid qilish",
                    url=product_webapp_url,
                )
            )
            reply_markup = InlineKeyboardMarkup(inline_keyboard=[[btn]])

            if not photos:
                raise ValueError("Mahsulot rasmi yo'q. Kanalga rasmsiz tovar chiqarilmaydi.")

            if len(photos) > 1:
                # Multiple clean product photos: send album to channel
                media_group: List[InputMediaPhoto] = []
                post_photos = photos[:10]
                for idx, p in enumerate(post_photos):
                    media_input = _get_media_input(p)
                    if idx == 0:
                        media_group.append(
                            InputMediaPhoto(
                                media=media_input,
                                caption=cap,
                                parse_mode="HTML",
                            )
                        )
                    else:
                        media_group.append(
                            InputMediaPhoto(
                                media=media_input,
                            )
                        )
                sent_msgs = await bot.send_media_group(
                    chat_id=channel_id,
                    media=media_group,
                )
                if isinstance(sent_msgs, (list, tuple)) and sent_msgs:
                    return sent_msgs[0].message_id
                return getattr(sent_msgs, "message_id", None)
            else:
                # Single clean product photo: send with attached inline action button
                photo_obj = _get_media_input(photos[0])
                msg = await bot.send_photo(
                    chat_id=channel_id,
                    photo=photo_obj,
                    caption=cap,
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
