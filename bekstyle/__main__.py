"""Run with: python -m bekstyle"""

import os
import asyncio
import logging
from aiohttp import web

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramAPIError, TelegramUnauthorizedError
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand
from aiogram.utils.token import TokenValidationError

from bekstyle import texts as t
from bekstyle.config import settings
from bekstyle.db import engine, init_db
from bekstyle.handlers import admin, admin_orders, admin_products, cart, catalog, common
from bekstyle.services import setup_code_is_safe
from bekstyle.visuals import ensure_visuals

logger = logging.getLogger("bekstyle")


async def start_healthcheck_server(port: int):
    """Render Web Service needs to bind to $PORT to pass port healthcheck, and cron-job.org pings it."""
    app = web.Application()

    async def handle_ping(request):
        return web.json_response({"status": "ok", "app": "BEK STYLE", "bot": "@bek_styleee_bot"})

    app.router.add_get("/", handle_ping)
    app.router.add_get("/health", handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info("Health check server listening on 0.0.0.0:%s", port)
    return runner


def build_dispatcher() -> Dispatcher:
    # shortcut: wizard/checkout steps reset on restart; use RedisStorage if that hurts
    dp = Dispatcher(storage=MemoryStorage())
    # Order matters: cancel/start first, customer screens, admin screens, catch-all last.
    dp.include_routers(
        common.router,
        catalog.router,
        cart.router,
        admin.router,
        admin_products.router,
        admin_orders.router,
        common.fallback_router,
    )
    return dp


async def configure_profile(bot: Bot) -> None:
    try:
        await bot.set_my_commands(
            [
                BotCommand(command="start", description=f"{t.BRAND} — bosh menyu"),
                BotCommand(command="admin", description="Admin panel"),
                BotCommand(command="cancel", description="Bekor qilish"),
            ]
        )
        await bot.set_my_short_description(f"{t.BRAND} — yigitlar uchun streetwear & casual 🔥")
        await bot.set_my_description(
            f"⚡ {t.BRAND}\nYigitlar uchun streetwear & casual.\nPinduoduodan buyurtma asosida — rasm, narx, rang va o'lcham bilan."
        )
    except TelegramAPIError as exc:  # profile texts are cosmetic; never block startup on them
        logger.warning("Bot profile setup skipped: %s", exc)


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    if not settings.BOT_TOKEN:
        raise SystemExit("BOT_TOKEN topilmadi: .env faylini to'ldiring (README.md ga qarang).")
    if not setup_code_is_safe():
        logger.warning("OWNER_SETUP_CODE 16 belgidan qisqa — egalikni olish havolasi ishlamaydi.")

    port = int(os.getenv("PORT", settings.PORT or 8000))
    health_runner = None
    try:
        health_runner = await start_healthcheck_server(port)
    except Exception as exc:
        logger.warning("Health check server could not be started on port %s: %s", port, exc)

    ensure_visuals()
    await init_db()
    try:
        bot = Bot(settings.BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    except TokenValidationError:
        raise SystemExit("BOT_TOKEN formati noto'g'ri: @BotFather bergan tokenni to'liq nusxalang.") from None
    dp = build_dispatcher()
    try:
        try:
            me = await bot.get_me()
        except TelegramUnauthorizedError:
            raise SystemExit("BOT_TOKEN noto'g'ri yoki bekor qilingan: @BotFather dan yangisini oling.") from None
        await configure_profile(bot)
        logger.info("%s bot ishga tushdi: @%s", t.BRAND, me.username)
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        if health_runner:
            await health_runner.cleanup()
        await bot.session.close()
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
