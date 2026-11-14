import asyncio
import hashlib
import hmac
import json
import logging
import time
from typing import Optional, Dict, Any

import httpx
from sqlalchemy import select

from api.config import settings
from db.models import Product, Category

logger = logging.getLogger("moonlight_cloud_sync")


def generate_admin_init_data(admin_id: int = 8643984824, first_name: str = "Otabek", username: str = "obidjonovic2") -> str:
    """Generates an HMAC-SHA256 signed X-Telegram-Init-Data header accepted by require_admin."""
    token = settings.BOT_TOKEN or ""
    if not token or token == "mock_bot_token_for_tests":
        return "dev_browser_mode"

    user_json = json.dumps({"id": admin_id, "first_name": first_name, "username": username}, separators=(",", ":"))
    auth_date = str(int(time.time()))
    data_dict = {"auth_date": auth_date, "user": user_json}
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(data_dict.items()))
    secret_key = hmac.new(b"WebAppData", token.encode("utf-8"), hashlib.sha256).digest()
    hash_val = hmac.new(secret_key, data_check_string.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"auth_date={auth_date}&user={user_json}&hash={hash_val}"


async def sync_product_to_cloud(product: Product) -> bool:
    """
    Asynchronously syncs a newly created product from local SQLite to the cloud Mini App (Render).
    Guarantees products uploaded via Telegram bot appear immediately in the Mini App.
    """
    base_url = (settings.WEBAPP_URL or "").rstrip("/")
    if not base_url or not base_url.startswith("https://"):
        return False

    headers = {"X-Telegram-Init-Data": generate_admin_init_data()}

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            # 1. Ensure category exists on cloud
            cat_slug = (product.category or "kiyim").lower()
            try:
                cat_chk = await client.get(f"{base_url}/api/categories")
                if cat_chk.is_success:
                    existing_cats = {c.get("slug") for c in cat_chk.json()}
                    if cat_slug not in existing_cats:
                        await client.post(
                            f"{base_url}/api/admin/categories",
                            json={
                                "slug": cat_slug,
                                "name": cat_slug.capitalize(),
                                "emoji": "🌸",
                                "sort_order": 10,
                            },
                            headers=headers,
                        )
            except Exception as e:
                logger.warning(f"Could not verify category {cat_slug} on cloud: {e}")

            # 2. Check if product already exists on cloud by title
            prods_chk = await client.get(f"{base_url}/api/products")
            if prods_chk.is_success:
                titles = {p.get("title", "").strip().lower() for p in prods_chk.json()}
                if product.title.strip().lower() in titles:
                    logger.info(f"Product '{product.title}' already exists on cloud.")
                    return True

            # 3. Create product on cloud
            payload = {
                "title": product.title,
                "description": product.description or "",
                "price": product.price,
                "old_price": product.old_price,
                "source_price": product.source_price,
                "category": cat_slug,
                "photos": product.photos or [],
                "sizes": product.sizes or ["Standart"],
                "colors": product.colors or ["Rasmda ko'rsatilgan"],
                "weight_grams": product.weight_grams,
                "in_stock": product.in_stock,
                "is_new": product.is_new,
                "is_hit": product.is_hit,
            }
            res = await client.post(f"{base_url}/api/admin/products", json=payload, headers=headers)
            if res.is_success:
                logger.info(f"Successfully synced product '{product.title}' to cloud Mini App! ({res.status_code})")
                return True
            else:
                logger.warning(f"Failed to sync product '{product.title}' to cloud: {res.status_code} - {res.text[:150]}")
                return False
    except Exception as exc:
        logger.warning(f"Cloud sync exception for product '{product.title}': {exc}")
        return False


async def run_render_keepalive_worker() -> None:
    """
    Pings the Render cloud deployment every 8 minutes.
    Prevents Render's free container from entering cold sleep (which causes 50s delays).
    Ensures the Mini App opens in <1 second at all times.
    """
    base_url = (settings.WEBAPP_URL or "").rstrip("/")
    if not base_url or not base_url.startswith("https://"):
        return

    logger.info(f"Starting Render keepalive worker for {base_url}...")
    while True:
        try:
            await asyncio.sleep(480)  # 8 minutes
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.get(f"{base_url}/api/settings")
                logger.info(f"Render keepalive ping: {res.status_code}")
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.debug(f"Render keepalive ping error (harmless): {e}")
