"""Run with: python -m bekstyle"""

import os
from aiogram import Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from bekstyle.handlers import admin, admin_orders, admin_products, cart, catalog, common
import uvicorn
from bekstyle.config import settings


def build_dispatcher() -> Dispatcher:
    """Build the bot dispatcher for the API lifespan and tests."""
    dp = Dispatcher(storage=MemoryStorage())
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

def main():
    port = int(os.getenv("PORT", settings.PORT or 8000))
    host = os.getenv("HOST", "0.0.0.0")

    # Run FastAPI app with lifespan starting aiogram bot
    uvicorn.run(
        "bekstyle.api.server:app",
        host=host,
        port=port,
        reload=False,
    )

if __name__ == "__main__":
    main()
