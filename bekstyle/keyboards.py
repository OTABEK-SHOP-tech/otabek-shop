from collections.abc import Callable

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    WebAppInfo,
)

from bekstyle import texts as t
from bekstyle.config import settings

Button = InlineKeyboardButton


def _rows(buttons: list[Button], width: int) -> list[list[Button]]:
    return [buttons[i : i + width] for i in range(0, len(buttons), width)]


def main_menu(is_admin: bool) -> ReplyKeyboardMarkup:
    rows = [
        [
            KeyboardButton(
                text="🛍 Do'konni ochish",
                web_app=WebAppInfo(url=settings.WEBAPP_URL),
            )
        ],
        [KeyboardButton(text=t.BTN_CATALOG), KeyboardButton(text=t.BTN_NEW)],
        [KeyboardButton(text=t.BTN_CART), KeyboardButton(text=t.BTN_ORDERS)],
        [KeyboardButton(text=t.BTN_CONTACT), KeyboardButton(text=t.BTN_CHANNEL)],
    ]
    if is_admin:
        rows.append([KeyboardButton(text=t.BTN_ADMIN)])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True, input_field_placeholder=f"{t.BRAND} — Streetwear & Casual")


def admin_menu() -> InlineKeyboardMarkup:
    """Admin inline menu used by the bot handlers."""
    return inline(
        [("➕ Mahsulot qo'shish", "ap:add"), ("📦 Mahsulotlar", "ap:list")],
        [("🧾 Buyurtmalar", "ao:list"), ("⚙️ Sozlamalar", "a:settings")],
    )


def start_inline_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🛍 Do'konni ochish (Mini App)",
                    web_app=WebAppInfo(url=settings.WEBAPP_URL),
                )
            ],
            [
                InlineKeyboardButton(text="🗂 Mahsulotlar katalogi", callback_data="catalog:browse"),
                InlineKeyboardButton(text="🛒 Savatcha", callback_data="cart:view"),
            ]
        ]
    )


def reply_kb(*labels: str, cancel: bool = True) -> ReplyKeyboardMarkup:
    rows = [[KeyboardButton(text=label)] for label in labels]
    if cancel:
        rows.append([KeyboardButton(text=t.BTN_CANCEL)])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def phone_kb(saved_phone: str | None) -> ReplyKeyboardMarkup:
    rows = [[KeyboardButton(text=t.BTN_SEND_PHONE, request_contact=True)]]
    if saved_phone:
        rows.append([KeyboardButton(text=saved_phone)])
    rows.append([KeyboardButton(text=t.BTN_CANCEL)])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def inline(*rows: list[tuple[str, str]]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[Button(text=x, callback_data=cb) for x, cb in row] for row in rows])


def categories_kb(items: list[tuple[int, str, int]]) -> InlineKeyboardMarkup:
    pairs = [(f"{label} • {count}", f"cat:{cid}:0") for cid, label, count in items]
    return grid(pairs, 2, [("🔥 Yangi kelganlar", "cat:0:0")])


def grid(pairs: list[tuple[str, str]], width: int, *tail: list[tuple[str, str]]) -> InlineKeyboardMarkup:
    buttons = [Button(text=x, callback_data=cb) for x, cb in pairs]
    tail_rows = [[Button(text=x, callback_data=cb) for x, cb in row] for row in tail]
    return InlineKeyboardMarkup(inline_keyboard=[*_rows(buttons, width), *tail_rows])


def picker_kb(options: list[str], callback_for: Callable[[int], str], back: str) -> InlineKeyboardMarkup:
    rows = [[Button(text=value, callback_data=callback_for(i))] for i, value in enumerate(options)]
    rows.append([Button(text="⬅️ Orqaga", callback_data=back)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def card_kb(product_id: int, category_id: int, position: int, total: int,
            in_stock: bool, photo_count: int, cart_count: int) -> InlineKeyboardMarkup:
    rows: list[list[Button]] = []
    if total > 1:
        rows.append([Button(text="◀️", callback_data=f"cat:{category_id}:{(position - 1) % total}"),
                     Button(text=f"{position + 1}/{total}", callback_data="noop"),
                     Button(text="▶️", callback_data=f"cat:{category_id}:{(position + 1) % total}")])
    if photo_count > 1:
        rows.append([Button(text="🖼 Barcha rasmlar", callback_data=f"ph:{product_id}")])
    if in_stock:
        rows.append([Button(text="🛒 Savatga qo'shish", callback_data=f"b:{product_id}:{category_id}:x:x")])
    rows.append([Button(text="🛍 Katalog", callback_data="cats"), Button(text=f"🛒 Savat ({cart_count})", callback_data="cart")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def cart_kb(item_ids: list[int]) -> InlineKeyboardMarkup:
    rows = [[Button(text="➖", callback_data=f"cq:{item_id}:-1"),
             Button(text="➕", callback_data=f"cq:{item_id}:1")] for item_id in item_ids]
    rows += [[Button(text="🗑 Savatni tozalash", callback_data="cclear")],
             [Button(text="✅ Buyurtma berish", callback_data="checkout")],
             [Button(text="🛍 Katalog", callback_data="cats")]]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def order_admin_kb(order_id: int, status: str, username: str | None = None) -> InlineKeyboardMarkup:
    from bekstyle.texts import next_status
    nxt = next_status(status)
    rows: list[list[Button]] = []
    if nxt:
        rows.append([Button(text=f"Holatni o'zgartirish -> {nxt}", callback_data=f"ord:{order_id}:{nxt}")])
    rows.append([
        Button(text="❌ Bekor qilish", callback_data=f"ord:{order_id}:cancelled"),
        Button(text="🗑 O'chirish", callback_data=f"ord:{order_id}:del"),
    ])
    if username:
        rows.append([Button(text="💬 Mijoz bilan yozishish", url=f"https://t.me/{username.lstrip('@')}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def order_receipt_admin_kb(order_id: int, username: str | None = None) -> InlineKeyboardMarkup:
    rows = [
        [
            Button(text="✅ To'lovni tasdiqlash", callback_data=f"pay:confirm:{order_id}"),
            Button(text="❌ Rad etish", callback_data=f"pay:reject:{order_id}"),
        ]
    ]
    if username:
        rows.append([Button(text="💬 Mijoz bilan yozishish", url=f"https://t.me/{username.lstrip('@')}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
