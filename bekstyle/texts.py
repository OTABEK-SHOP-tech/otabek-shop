"""BEK STYLE brand voice: every customer- and admin-facing string and formatter lives here."""

import re
from datetime import UTC, datetime, timedelta, timezone
from html import escape
from typing import Any

BRAND = "BEK STYLE"
LINE = "━━━━━━━━━━━━"
TASHKENT_TZ = timezone(timedelta(hours=5))  # Uzbekistan has no DST
CAPTION_LIMIT = 1024

# Reply keyboard buttons (customer)
BTN_CATALOG = "🛍 Katalog"
BTN_NEW = "🔥 Yangi"
BTN_CART = "🛒 Savat"
BTN_ORDERS = "📦 Buyurtmalarim"
BTN_CONTACT = "📞 Aloqa"
BTN_CHANNEL = "📢 Kanal"
BTN_ADMIN = "👑 Admin panel"
BTN_CANCEL = "❌ Bekor qilish"
BTN_SKIP = "⏭ O'tkazish"
BTN_DONE_PHOTOS = "✅ Tayyor"
BTN_SEND_PHONE = "📱 Raqamni yuborish"

SIZE_PRESETS = [
    "S, M, L, XL, XXL",
    "M, L, XL",
    "28, 29, 30, 31, 32, 33, 34",
    "40, 41, 42, 43, 44",
    "Universal",
]

# status -> (label, message to the customer); order matters: it is the normal flow
ORDER_STATUSES: dict[str, tuple[str, str]] = {
    "pending_payment": ("⏳ To'lov kutilmoqda", "Kartaga to'lov qiling va to'lov chekini yuboring."),
    "payment_review": ("🔍 To'lov tekshirilmoqda", "Chekingiz yuborildi. Admin to'lovni tekshirmoqda."),
    "paid": ("💳 To'landi", "To'lov tasdiqlandi! Buyurtmangiz qabul qilindi va tayyorlanmoqda."),
    "payment_rejected": ("❌ To'lov rad etildi", "To'lov cheki tasdiqlanmadi. Iltimos, yangi chek yuklang."),
    "new": ("🆕 Yangi", "Qabul qilindi — to'lov tekshiruvi kutilmoqda."),
    "accepted": ("✅ Tasdiqlandi", "To'lov qabul qilindi."),
    "ordered": ("🛒 Pinduoduoga berildi", "Buyurtmangiz yo'lga chiqishga tayyorlanmoqda. Yetkazish: {delivery}."),
    "shipping": ("🚚 Yo'lda", "Yaqin kunlarda O'zbekistonga yetib keladi."),
    "arrived": ("📍 Yetib keldi", "Buyurtmangiz yetib keldi. Admin topshirish va cargo hisobi uchun bog'lanadi."),
    "done": ("🏁 Topshirildi", "{brand}ni tanlaganingiz uchun rahmat 🖤"),
    "cancelled": ("❌ Bekor qilindi", "Savol bo'lsa, admin bilan bog'laning."),
}
STATUS_FLOW = [
    "pending_payment",
    "payment_review",
    "paid",
    "ordered",
    "shipping",
    "arrived",
    "done",
]
FINAL_STATUSES = {"done", "cancelled"}


def format_price(amount: int) -> str:
    return f"{int(amount):,}".replace(",", " ") + " so'm"


def format_dt(value: datetime) -> str:
    aware = value if value.tzinfo else value.replace(tzinfo=UTC)  # SQLite returns naive UTC
    return aware.astimezone(TASHKENT_TZ).strftime("%d.%m.%Y %H:%M")


def hashtag(name: str) -> str:
    return "#" + re.sub(r"\W+", "_", name.lower()).strip("_")


def clip(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def status_label(status: str) -> str:
    return ORDER_STATUSES.get(status, (status, ""))[0]


def next_status(status: str) -> str | None:
    if status not in STATUS_FLOW or status == STATUS_FLOW[-1]:
        return None
    return STATUS_FLOW[STATUS_FLOW.index(status) + 1]


def greeting(name: str) -> str:
    return (
        f"🖤 <b>{BRAND}</b> — xush kelibsiz, {escape(name)}!\n\n"
        "Yigitlar uchun streetwear & casual.\n"
        "Pinduoduodan buyurtma asosida — sifatli va hamyonbop.\n\n"
        f"👇 <b>{BTN_CATALOG}</b> — o'zingizga mosini tanlang."
    )


def attrs_lines(colors: list[str], sizes: list[str]) -> list[str]:
    lines: list[str] = []
    if colors:
        lines.append(f"🎨 Rang: {escape(', '.join(colors))}")
    if sizes:
        lines.append(f"📏 O'lcham: {escape(', '.join(sizes))}")
    return lines


def product_caption(
    title: str,
    price: int,
    colors: list[str],
    sizes: list[str],
    description: str,
    delivery: str,
    in_stock: bool,
) -> str:
    lines = [
        f"<b>{escape(title)}</b>",
        LINE,
        f"💵 <b>{format_price(price)}</b>",
        *attrs_lines(colors, sizes),
        f"🚚 Yetkazish: {escape(delivery)}",
    ]
    if description:
        lines += ["", escape(clip(description, 400))]
    lines += ["", "🟢 Buyurtmaga ochiq" if in_stock else "⚪️ Hozircha tugagan"]
    return clip("\n".join(lines), CAPTION_LIMIT)


def channel_caption(
    title: str,
    price: int,
    category_name: str,
    colors: list[str],
    sizes: list[str],
    description: str,
    delivery: str,
) -> str:
    lines = [
        f"🖤 <b>{BRAND}</b>  {escape(hashtag(category_name))}",
        "",
        f"<b>{escape(title)}</b>",
        LINE,
        f"💵 Narx: <b>{format_price(price)}</b>",
        *attrs_lines(colors, sizes),
        f"🚚 Yetkazish: {escape(delivery)}",
    ]
    if description:
        lines += ["", escape(clip(description, 300))]
    lines += ["", "🟢 Buyurtma — pastdagi tugma orqali 👇"]
    return clip("\n".join(lines), CAPTION_LIMIT)


def item_variant(color: str | None, size: str | None) -> str:
    return " / ".join(v for v in (color, size) if v)


def items_block(items: list[dict[str, Any]]) -> str:
    rows: list[str] = []
    for i, it in enumerate(items, 1):
        variant = item_variant(it.get("color"), it.get("size"))
        variant_txt = f" — {escape(variant)}" if variant else ""
        subtotal = int(it["price"]) * int(it["qty"])
        rows.append(
            f"{i}. <b>{escape(str(it['title']))}</b>{variant_txt}\n"
            f"    {it['qty']} × {format_price(int(it['price']))} = {format_price(subtotal)}"
        )
    return "\n".join(rows)


def order_text(
    order_id: int,
    status: str,
    items: list[dict[str, Any]],
    total: int,
    created_at: datetime,
    customer: str = "",
    selected_card: str | None = None,
    cargo_price: int | None = None,
    reject_reason: str | None = None,
) -> str:
    """customer: pre-escaped HTML block with name/phone/address; empty for the customer's own view."""
    parts = [f"🧾 <b>Buyurtma #{order_id}</b> · {status_label(status)}"]
    if customer:
        parts.append(customer)
    parts += [
        LINE,
        items_block(items),
        LINE,
        f"💵 Hozir to'lanadigan: <b>{format_price(total)}</b>",
    ]
    if selected_card:
        parts.append(f"💳 Tanlangan karta: <code>{escape(selected_card)}</code>")
    if cargo_price is not None:
        parts.append(f"📦 Cargo to'lovi: <b>{format_price(cargo_price)}</b>")
    else:
        parts.append("📦 Cargo haqi: <i>Tortilgandan keyin alohida hisoblanadi</i>")
    if reject_reason:
        parts.append(f"⚠️ Rad etish sababi: <i>{escape(reject_reason)}</i>")
    parts.append(f"🕒 {format_dt(created_at)}")
    return "\n".join(parts)


def customer_block(user_id: int, name: str, username: str | None, phone: str, address: str) -> str:
    uname = f" (@{escape(username)})" if username else ""
    return f'👤 <a href="tg://user?id={user_id}">{escape(name)}</a>{uname}\n📱 {escape(phone)}\n📍 {escape(address)}'


def status_message(order_id: int, status: str, delivery: str, contact: str) -> str:
    label, body = ORDER_STATUSES[status]
    text = f"🖤 <b>{BRAND}</b> · Buyurtma #{order_id}\n{label}\n\n{body.format(delivery=delivery, brand=BRAND)}"
    return text + (f"\n\n📞 Aloqa: @{contact}" if contact else "")
