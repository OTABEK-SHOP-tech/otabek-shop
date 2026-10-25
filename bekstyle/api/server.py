import os
import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand, MenuButtonWebApp, WebAppInfo

from bekstyle import texts as t
from bekstyle.config import settings
from bekstyle.db import engine, init_db
from bekstyle.visuals import ensure_visuals
from bekstyle.api.routes import categories, products, cart, orders, user, settings as settings_route, media

logger = logging.getLogger("bekstyle")

bot_instance: Bot | None = None
bot_task: asyncio.Task | None = None


def get_dispatcher() -> Dispatcher:
    from bekstyle.__main__ import build_dispatcher
    return build_dispatcher()


async def setup_bot_profile(bot: Bot) -> None:
    try:
        webapp_url = settings.WEBAPP_URL
        # Set Telegram Menu button to open Mini App directly!
        await bot.set_chat_menu_button(
            menu_button=MenuButtonWebApp(
                text="🛍 Do'kon",
                web_app=WebAppInfo(url=webapp_url),
            )
        )
        await bot.set_my_commands(
            [
                BotCommand(command="start", description="⚡ BEK STYLE — Bosh menyu"),
                BotCommand(command="admin", description="👑 Admin panel"),
                BotCommand(command="cancel", description="❌ Bekor qilish"),
            ]
        )
        await bot.set_my_short_description(f"{t.BRAND} — yigitlar kiyimi va aksessuarlari")
        await bot.set_my_description(
            f"⚡ {t.BRAND}\nYigitlar uchun kiyim va aksessuarlar do‘koni.\n"
            f"Mahsulotni tanlang, buyurtma bering va to‘lov chekini yuboring."
        )
    except Exception as exc:
        logger.warning("Bot profile/menu button setup failed: %s", exc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global bot_instance, bot_task

    logger.info("Initializing BEK STYLE database & visuals...")
    ensure_visuals()
    await init_db()

    # Start Telegram Bot Polling in background task if BOT_TOKEN is set
    if settings.BOT_TOKEN:
        try:
            bot = Bot(settings.BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
            bot_instance = bot
            me = await bot.get_me()
            await setup_bot_profile(bot)
            logger.info("Telegram Bot active: @%s (ID: %s)", me.username, me.id)

            dp = get_dispatcher()

            async def poll():
                try:
                    logger.info("Starting Telegram bot polling loop...")
                    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
                except asyncio.CancelledError:
                    pass
                except Exception as e:
                    logger.error("Bot polling error: %s", e)

            bot_task = asyncio.create_task(poll())
        except Exception as exc:
            logger.error("Failed to start bot: %s", exc)
    else:
        logger.warning("BOT_TOKEN is not set; running API only.")

    yield

    # Shutdown
    logger.info("Shutting down BEK STYLE application...")
    if bot_task and not bot_task.done():
        bot_task.cancel()
        try:
            await bot_task
        except asyncio.CancelledError:
            pass

    if bot_instance:
        await bot_instance.session.close()

    await engine.dispose()
    logger.info("Shutdown complete.")


def create_app() -> FastAPI:
    app = FastAPI(
        title="BEK STYLE Mini App API",
        version="2.0.0",
        lifespan=lifespan,
    )

    # CORS for Telegram Mini App
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include API routes
    app.include_router(products.router, prefix="/api")
    app.include_router(categories.router, prefix="/api")
    app.include_router(cart.router, prefix="/api")
    app.include_router(orders.router, prefix="/api")
    app.include_router(user.router, prefix="/api")
    app.include_router(settings_route.router, prefix="/api")
    app.include_router(media.router, prefix="/api")

    # Health check for Render and cron-job.org
    @app.get("/health")
    @app.get("/api/health")
    async def health():
        return {"status": "ok", "app": "BEK STYLE", "bot": "@bek_styleee_bot"}

    # Serve built React Mini App from webapp/dist
    webapp_dist = Path(__file__).resolve().parent.parent.parent / "webapp" / "dist"
    if not webapp_dist.is_dir():
        # Fallback to local bekstyle/static if bundled
        webapp_dist = Path(__file__).resolve().parent.parent / "static"

    if webapp_dist.is_dir():
        assets_dir = webapp_dist / "assets"
        if assets_dir.is_dir():
            app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

        @app.get("/{full_path:path}")
        async def serve_spa(full_path: str, request: Request):
            # Don't intercept api routes
            if full_path.startswith("api/"):
                return JSONResponse({"detail": "Not Found"}, status_code=404)

            file_path = (webapp_dist / full_path).resolve()
            if not file_path.is_relative_to(webapp_dist.resolve()):
                return JSONResponse({"detail": "Not Found"}, status_code=404)
            if file_path.is_file():
                return FileResponse(str(file_path))

            index_file = webapp_dist / "index.html"
            if index_file.is_file():
                return FileResponse(str(index_file), headers={"Cache-Control": "no-cache"})

            return JSONResponse({"status": "ok", "app": "BEK STYLE", "detail": "Webapp building..."}, status_code=200)

    return app


app = create_app()
