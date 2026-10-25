from collections.abc import Callable

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

from bekstyle import texts as t

Button = InlineKeyboardButton


def _rows(buttons: list[Button], width: int) -> list[list[Button]]:
    return [buttons[i : i + width] for i in range(0, len(buttons), width)]


def main_menu(is_admin: bool) -> ReplyKeyboardMarkup:
    rows = [
        [KeyboardButton(text=t.BTN_CATALOG), KeyboardButton(text=t.BTN_NEW)],
        [KeyboardButton(text=t.BTN_CART), KeyboardButton(text=t.BTN_ORDERS)],
        [KeyboardButton(text=t.BTN_CONTACT), KeyboardButton(text=t.BTN_CHANNEL)],
    ]
    if is_admin:
        rows.append([KeyboardButton(text=t.BTN_ADMIN)])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True, input_field_placeholder=f"{t.BRAND} 🖤")


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
    """inline([("Text", "callback"), ...], ...) — one list per row."""
    return InlineKeyboardMarkup(inline_keyboard=[[Button(text=x, callback_data=cb) for x, cb in row] for row in rows])


def categories_kb(items: list[tuple[int, str, int]]) -> InlineKeyboardMarkup:
    """items: (category_id, label, count)."""
    pairs = [(f"{label} · {count}", f"cat:{cid}:0") for cid, label, count in items]
    return grid(pairs, 2, [("🔥 Yangi kelganlar", "cat:0:0")])


def grid(pairs: list[tuple[str, str]], width: int, *tail: list[tuple[str, str]]) -> InlineKeyboardMarkup:
    """(text, callback) pairs laid out `width` per row, then fixed `tail` rows."""
    buttons = [Button(text=x, callback_data=cb) for x, cb in pairs]
    tail_rows = [[Button(text=x, callback_data=cb) for x, cb in row] for row in tail]
    return InlineKeyboardMarkup(inline_keyboard=[*_rows(buttons, width), *tail_rows])


def card_kb(
    pid: int,
    cid: int,
    idx: int,
    total: int,
    in_stock: bool,
    photo_count: int,
    cart_n: int,
) -> InlineKeyboardMarkup:
    rows: list[list[Button]] = []
    if in_stock:
        rows.append([Button(text="🛒 Savatga qo'shish", callback_data=f"b:{pid}:{cid}:x:x")])
    if photo_count > 1:
        rows.append([Button(text=f"🖼 Barcha rasmlar ({photo_count})", callback_data=f"ph:{pid}")])
    if total > 1:
        rows.append(
            [
                Button(text="◀️", callback_data=f"cat:{cid}:{(idx - 1) % total}"),
                Button(text=f"{idx + 1} / {total}", callback_data="noop"),
                Button(text="▶️", callback_data=f"cat:{cid}:{(idx + 1) % total}"),
            ]
        )
    cart_label = f"🛒 Savat ({cart_n})" if cart_n else "🛒 Savat"
    rows.append(
        [
            Button(text=cart_label, callback_data="cart"),
            Button(text="⬅️ Bo'limlar", callback_data="cats"),
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def picker_kb(options: list[str], make_cb: Callable[[int], str], back_cb: str) -> InlineKeyboardMarkup:
    buttons = [Button(text=opt, callback_data=make_cb(i)) for i, opt in enumerate(options)]
    return InlineKeyboardMarkup(
        inline_keyboard=[
            *_rows(buttons, 3),
            [Button(text="⬅️ Orqaga", callback_data=back_cb)],
        ]
    )


def cart_kb(item_ids: list[int]) -> InlineKeyboardMarkup:
    rows = [
        [
            Button(text=f"➖ {n}", callback_data=f"cq:{item_id}:-1"),
            Button(text=f"➕ {n}", callback_data=f"cq:{item_id}:1"),
            Button(text=f"🗑 {n}", callback_data=f"cq:{item_id}:0"),
        ]
        for n, item_id in enumerate(item_ids, 1)
    ]
    rows.append(
        [
            Button(text="🧹 Tozalash", callback_data="cclear"),
            Button(text="🛍 Katalog", callback_data="cats"),
        ]
    )
    rows.append([Button(text="✅ Buyurtma berish", callback_data="checkout")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_menu() -> InlineKeyboardMarkup:
    return inline(
        [("➕ Mahsulot qo'shish", "ap:add"), ("📦 Mahsulotlar", "apl:0")],
        [("🧾 Buyurtmalar", "aol:active"), ("🗂 Bo'limlar", "a:cats")],
        [("📣 Xabar yuborish", "a:bc"), ("📊 Statistika", "a:stats")],
        [("⚙️ Sozlamalar", "a:settings")],
    )


def order_admin_kb(order_id: int, status: str, username: str | None) -> InlineKeyboardMarkup:
    rows: list[list[Button]] = []
    following = t.next_status(status)
    if following:
        rows.append(
            [
                Button(
                    text=f"➡️ {t.status_label(following)}",
                    callback_data=f"os:{order_id}:{following}",
                )
            ]
        )
    if status not in t.FINAL_STATUSES:
        rows.append([Button(text="❌ Bekor qilish", callback_data=f"oc:{order_id}")])
    if username:
        rows.append([Button(text="💬 Mijozga yozish", url=f"https://t.me/{username}")])
    rows.append([Button(text="⬅️ Buyurtmalar", callback_data="aol:active")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
