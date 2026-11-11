from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    WebAppInfo,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from api.config import settings

CONTEST_BUTTON_TEXT = "🎁 Konkursda qatnashish"
# Users who never re-sent /start still have the old label cached in their keyboard.
LEGACY_CONTEST_BUTTON_TEXT = "🎁 Konkurs"
RATING_BUTTON_TEXT = "🏆 Reyting"


def get_main_reply_keyboard(webapp_url: str = settings.WEBAPP_URL) -> ReplyKeyboardMarkup:
    """
    Main persistent reply keyboard for customers.
    """
    if webapp_url and webapp_url.startswith("https://"):
        first_btn = KeyboardButton(
            text="🛍️ Do'konni ochish",
            web_app=WebAppInfo(url=webapp_url),
        )
    else:
        first_btn = KeyboardButton(text="🛍️ Do'konni ochish")

    return ReplyKeyboardMarkup(
        keyboard=[
            [first_btn],
            [
                KeyboardButton(text=CONTEST_BUTTON_TEXT),
                KeyboardButton(text=RATING_BUTTON_TEXT),
            ],
            [
                KeyboardButton(text="🆕 Yangi mahsulotlar"),
                KeyboardButton(text="⭐ Fikrlar"),
            ],
            [
                KeyboardButton(text="💌 Admin bilan bog'lanish"),
                KeyboardButton(text="📢 Kanal"),
            ],
        ],
        resize_keyboard=True,
    )


def make_webapp_inline_btn(text: str, url: str) -> InlineKeyboardButton:
    """Creates an inline button, using WebAppInfo if https, or url fallback if http."""
    if url and url.startswith("https://"):
        return InlineKeyboardButton(text=text, web_app=WebAppInfo(url=url))
    return InlineKeyboardButton(text=text, url=url or "http://localhost:8001")


def get_admin_main_keyboard() -> InlineKeyboardMarkup:
    """
    Main menu inline keyboard for /admin command.
    """
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🎁 Konkurs boshqaruvi", callback_data="admin_contest_menu"),
                InlineKeyboardButton(text="➕ Yangi mahsulot", callback_data="admin_add_product"),
            ],
            [
                InlineKeyboardButton(text="📦 Mahsulotlar", callback_data="admin_list_products"),
                InlineKeyboardButton(text="🗂 Kategoriyalar", callback_data="admin_categories"),
            ],
            [
                InlineKeyboardButton(text="⭐ Fikrlar", callback_data="admin_reviews"),
                InlineKeyboardButton(text="🧾 Buyurtmalar", callback_data="admin_orders"),
            ],
            [
                InlineKeyboardButton(text="📊 Statistika", callback_data="admin_stats"),
                InlineKeyboardButton(text="📣 Xabar yuborish (broadcast)", callback_data="admin_broadcast"),
            ],
            [
                InlineKeyboardButton(text="⚙️ Sozlamalar", callback_data="admin_settings"),
            ],
            [
                InlineKeyboardButton(
                    text="👑 Mini App Admin Panel",
                    web_app=WebAppInfo(url=f"{settings.WEBAPP_URL}?tab=admin"),
                )
            ]
        ]
    )
