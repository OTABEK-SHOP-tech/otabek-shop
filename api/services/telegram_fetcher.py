import os
import re
import logging
from html import unescape
from pathlib import Path
from typing import List, Dict, Any, Optional
import httpx

from api.config import settings

logger = logging.getLogger(__name__)

# Regex for matching public channel and private group/channel message links
# Matches:
# https://t.me/channel_name/123
# https://t.me/s/channel_name/123
# http://telegram.me/channel_name/123
# t.me/channel_name/123
# t.me/c/1234567890/123
# @channel_name/123
TG_POST_LINK_RE = re.compile(
    r"(?:https?://)?(?:www\.)?(?:t\.me|telegram\.me|telegram\.dog)/(?:s/)?(?:c/(\d+)|([a-zA-Z0-9_]{3,}))/(\d+)(?:\?[^\s]*)?",
    re.IGNORECASE,
)
AT_POST_LINK_RE = re.compile(
    r"@([a-zA-Z0-9_]{3,})/(\d+)",
    re.IGNORECASE,
)


def extract_telegram_post_links(text: str) -> List[Dict[str, Any]]:
    """
    Extracts all Telegram post links from text.
    Returns list of dicts:
    [{'url': full_match, 'is_private': bool, 'chat_ref': 'sakura_shop_uz' or '123456', 'message_id': 123}]
    """
    if not text:
        return []
    matches = []
    seen = set()

    for m in TG_POST_LINK_RE.finditer(text):
        full_url = m.group(0).rstrip(".,;!?:")
        c_id = m.group(1)
        public_name = m.group(2)
        msg_id = int(m.group(3))
        key = (c_id or public_name, msg_id)
        if key in seen:
            continue
        seen.add(key)
        if c_id:
            matches.append({
                "url": full_url,
                "is_private": True,
                "chat_ref": c_id,
                "message_id": msg_id,
            })
        elif public_name:
            matches.append({
                "url": full_url,
                "is_private": False,
                "chat_ref": public_name,
                "message_id": msg_id,
            })

    # Also check @channel/123 format
    for m in AT_POST_LINK_RE.finditer(text):
        public_name = m.group(1)
        msg_id = int(m.group(2))
        key = (public_name, msg_id)
        if key in seen:
            continue
        seen.add(key)
        matches.append({
            "url": f"https://t.me/{public_name}/{msg_id}",
            "is_private": False,
            "chat_ref": public_name,
            "message_id": msg_id,
        })

    return matches


def get_absolute_media_dir() -> Path:
    """Returns resolved absolute path to media cache directory."""
    raw = getattr(settings, "MEDIA_CACHE_DIR", "./media_cache")
    if os.path.isabs(raw):
        p = Path(raw)
    else:
        # Resolve relative to project root
        base = Path(__file__).resolve().parent.parent.parent
        p = base / raw
    p.mkdir(parents=True, exist_ok=True)
    return p


async def download_image_to_cache(image_url: str, dest_filename: str) -> Optional[str]:
    """
    Downloads an image from URL and saves it to MEDIA_CACHE_DIR.
    Returns the relative filename on success, or None on failure.
    """
    media_dir = get_absolute_media_dir()
    dest_path = media_dir / dest_filename

    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            resp = await client.get(
                image_url,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
            )
            if resp.status_code == 200 and resp.content:
                dest_path.write_bytes(resp.content)
                logger.info(f"Downloaded post image to {dest_path} ({len(resp.content)} bytes)")
                return dest_filename
    except Exception as e:
        logger.warning(f"Failed to download image {image_url}: {e}")
    return None


async def fetch_telegram_post_embed(channel_username: str, message_id: int) -> Dict[str, Any]:
    """
    Fetches a public Telegram channel post via its web widget embed (t.me/<channel>/<msg_id>?embed=1).
    Extracts the post text, media images, and downloads the images to local media cache.
    """
    clean_username = channel_username.lstrip("@").strip()
    embed_url = f"https://t.me/{clean_username}/{message_id}?embed=1"

    result: Dict[str, Any] = {
        "success": False,
        "channel": clean_username,
        "message_id": message_id,
        "raw_text": "",
        "photos": [],
        "error": None,
    }

    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            resp = await client.get(
                embed_url,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
            )
            if resp.status_code != 200:
                result["error"] = f"Telegram embed returned status {resp.status_code}"
                return result

            html = resp.text

            # 1. Check if post was not found or deleted
            if "Post not found" in html or "tgme_widget_message_error" in html:
                result["error"] = "Post topilmadi yoki o'chirilgan."
                return result

            # 2. Extract text from <div class="tgme_widget_message_text ...">
            m_text = re.search(r'class="tgme_widget_message_text[^"]*"[^>]*>(.*?)</div>', html, re.DOTALL)
            extracted_text = ""
            if m_text:
                raw_html = m_text.group(1)
                # Replace <br> or <br/> with newline
                with_newlines = re.sub(r'<br\s*/?>', '\n', raw_html)
                # Strip all HTML tags
                without_tags = re.sub(r'<[^>]+>', '', with_newlines)
                extracted_text = unescape(without_tags).strip()
            result["raw_text"] = extracted_text

            # 3. Extract photo background-images
            # Matches background-image:url('...') or background-image:url("...")
            photo_urls = re.findall(r"background-image:url\(['\"]?([^'\")]+)['\"]?\)", html)
            # Filter valid image URLs
            valid_urls = [u for u in photo_urls if u.startswith("http")]

            # Deduplicate preserving order
            seen = set()
            unique_urls = []
            for u in valid_urls:
                if u not in seen:
                    seen.add(u)
                    unique_urls.append(u)

            # Download photos into media cache
            downloaded_photos: List[str] = []
            for idx, img_url in enumerate(unique_urls[:10]):
                ext = ".jpg"
                if ".png" in img_url.lower():
                    ext = ".png"
                elif ".webp" in img_url.lower():
                    ext = ".webp"
                dest_name = f"import_{clean_username}_{message_id}_{idx}{ext}"
                saved = await download_image_to_cache(img_url, dest_name)
                if saved:
                    downloaded_photos.append(saved)
                else:
                    # Keep URL as fallback
                    downloaded_photos.append(img_url)

            result["photos"] = downloaded_photos
            result["success"] = bool(extracted_text or downloaded_photos)
            if not result["success"]:
                result["error"] = "Postdan matn yoki rasm ajratib bo'lmadi."
            return result

    except Exception as e:
        logger.error(f"Error fetching telegram embed for {clean_username}/{message_id}: {e}")
        result["error"] = str(e)
        return result
