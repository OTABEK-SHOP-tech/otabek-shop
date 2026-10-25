"""Business rules without Telegram I/O, so they are testable against a plain session."""

import hmac
import math
import re
from dataclasses import dataclass
from typing import Any

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from bekstyle.config import settings
from bekstyle.db import Admin, CartItem, Category, Order, Product, User
from bekstyle.texts import FINAL_STATUSES, next_status

MIN_SETUP_CODE_LENGTH = 16
MIN_PRICE_SOM = 1000
MAX_QTY = 10
NEW_ARRIVALS_LIMIT = 20

_YUAN_RE = re.compile(r"([0-9]+(?:[.,][0-9]{1,2})?)\s*(?:¥|￥|yuan|cny|юань|y)")
_SOM_SUFFIX_RE = re.compile(r"\s*(?:so['ʻ’`]?m|сум)$")


# ---------- pricing ----------
@dataclass(frozen=True)
class PriceInput:
    price: int  # sale price, so'm
    cost_cny: float | None  # set only when the admin typed a Pinduoduo price in yuan


def round_up_thousand(value: float) -> int:
    return int(math.ceil(round(value, 2) / 1000) * 1000)


def sale_price_from_yuan(cny: float, yuan_rate: int, markup_percent: int) -> int:
    return round_up_thousand(cny * yuan_rate * (1 + markup_percent / 100))


def parse_price_input(text: str, yuan_rate: int, markup_percent: int) -> PriceInput | None:
    """'79¥' / '79 yuan' -> sale price with markup; '189000' / '189 000 so'm' -> as is."""
    raw = text.strip().lower()
    yuan = _YUAN_RE.fullmatch(raw)
    if yuan:
        cny = float(yuan.group(1).replace(",", "."))
        return PriceInput(sale_price_from_yuan(cny, yuan_rate, markup_percent), cny) if cny > 0 else None
    digits = re.sub(r"[\s.,]", "", _SOM_SUFFIX_RE.sub("", raw))
    if not re.fullmatch(r"[0-9]+", digits):
        return None
    price = int(digits)
    # A bare "79" is almost always a forgotten ¥, not a 79 so'm shirt.
    return PriceInput(price, None) if price >= MIN_PRICE_SOM else None


def margin_som(price: int, cost_cny: float | None, yuan_rate: int) -> int | None:
    return None if cost_cny is None else price - round(cost_cny * yuan_rate)


def parse_list(text: str) -> list[str]:
    return [part.strip()[:32] for part in text.split(",") if part.strip()][:12]


def validate_setting(key: str, raw: str) -> str | None:
    """Normalized value for an admin-editable setting, or None if invalid."""
    value = raw.strip()
    if key == "contact_username":
        match = re.fullmatch(r"@?([A-Za-z][A-Za-z0-9_]{4,31})", value)
        return match.group(1) if match else None
    if key == "yuan_rate":
        return value if re.fullmatch(r"[0-9]{3,6}", value) else None
    if key == "markup_percent":
        return value if re.fullmatch(r"[0-9]{1,3}", value) and int(value) <= 500 else None
    if key == "delivery_text":
        return value if 2 <= len(value) <= 40 else None
    return None


def parse_category_input(text: str) -> tuple[str, str] | None:
    """'👕 Futbolkalar' -> ('👕', 'Futbolkalar'); a name without emoji gets a neutral marker."""
    parts = text.strip().split(maxsplit=1)
    if len(parts) == 2 and not any(ch.isalnum() for ch in parts[0]):
        emoji, name = parts[0][:8], parts[1].strip()
    else:
        emoji, name = "▫️", text.strip()
    return (emoji, name) if 2 <= len(name) <= 40 else None


# ---------- catalog ----------
async def catalog_product_ids(session: AsyncSession, category_id: int) -> list[int]:
    """category_id 0 = new arrivals across all categories."""
    query = select(Product.id).where(Product.in_stock.is_(True)).order_by(Product.created_at.desc(), Product.id.desc())
    query = query.where(Product.category_id == category_id) if category_id else query.limit(NEW_ARRIVALS_LIMIT)
    return list((await session.scalars(query)).all())


async def categories_with_counts(session: AsyncSession, in_stock_only: bool) -> list[tuple[Category, int]]:
    join_on = Product.category_id == Category.id
    if in_stock_only:
        join_on = join_on & Product.in_stock.is_(True)
    rows = await session.execute(
        select(Category, func.count(Product.id))
        .outerjoin(Product, join_on)
        .group_by(Category.id)
        .order_by(Category.sort_order, Category.id)
    )
    return [(cat, int(count)) for cat, count in rows.all()]


# ---------- cart ----------
async def get_cart(session: AsyncSession, user_id: int) -> list[CartItem]:
    rows = await session.scalars(select(CartItem).where(CartItem.user_id == user_id).order_by(CartItem.id))
    return list(rows.unique().all())


async def cart_count(session: AsyncSession, user_id: int) -> int:
    return int(
        await session.scalar(select(func.coalesce(func.sum(CartItem.qty), 0)).where(CartItem.user_id == user_id))
    )


async def add_to_cart(
    session: AsyncSession,
    user_id: int,
    product_id: int,
    color: str | None,
    size: str | None,
) -> int:
    """Adds one piece (merging same variant) and returns the new cart count."""
    existing = await session.scalar(
        select(CartItem).where(
            CartItem.user_id == user_id,
            CartItem.product_id == product_id,
            CartItem.color == color,
            CartItem.size == size,
        )
    )
    if existing:
        existing.qty = min(existing.qty + 1, MAX_QTY)
    else:
        session.add(CartItem(user_id=user_id, product_id=product_id, color=color, size=size, qty=1))
    await session.commit()
    return await cart_count(session, user_id)


async def change_cart_qty(session: AsyncSession, user_id: int, item_id: int, delta: int) -> None:
    """delta 0 removes the line; qty stays within 1..MAX_QTY."""
    item = await session.get(CartItem, item_id)
    if not item or item.user_id != user_id:
        return
    if delta == 0:
        await session.delete(item)
    else:
        item.qty = max(1, min(item.qty + delta, MAX_QTY))
    await session.commit()


async def clear_cart(session: AsyncSession, user_id: int) -> None:
    await session.execute(delete(CartItem).where(CartItem.user_id == user_id))
    await session.commit()


def cart_snapshot(items: list[CartItem]) -> list[dict[str, Any]]:
    return [
        {
            "product_id": it.product_id,
            "title": it.product.title,
            "price": it.product.price,
            "color": it.color,
            "size": it.size,
            "qty": it.qty,
        }
        for it in items
    ]


def snapshot_total(items: list[dict[str, Any]]) -> int:
    return sum(int(it["price"]) * int(it["qty"]) for it in items)


# ---------- orders ----------
async def create_order_from_cart(
    session: AsyncSession,
    user_id: int,
    name: str,
    username: str | None,
    phone: str,
    address: str,
) -> tuple[Order | None, int]:
    """Returns (order or None if nothing orderable, number of sold-out lines dropped)."""
    items = await get_cart(session, user_id)
    available = [it for it in items if it.product.in_stock]
    if not available:
        return None, len(items)
    snapshot = cart_snapshot(available)
    order = Order(
        user_id=user_id,
        customer_name=name,
        customer_username=username,
        phone=phone,
        address=address,
        items=snapshot,
        total=snapshot_total(snapshot),
        status="new",
    )
    session.add(order)
    user = await session.get(User, user_id)
    if user:
        user.phone = phone
    await session.execute(delete(CartItem).where(CartItem.user_id == user_id))
    await session.commit()
    return order, len(items) - len(available)


def can_move(current: str, target: str) -> bool:
    if target == "cancelled":
        return current not in FINAL_STATUSES
    return next_status(current) == target


async def change_order_status(session: AsyncSession, order_id: int, target: str) -> Order | None:
    """Conditional update, so two admins pressing the same button cannot both apply it."""
    order = await session.get(Order, order_id)
    if not order or not can_move(order.status, target):
        return None
    result = await session.execute(
        update(Order).where(Order.id == order_id, Order.status == order.status).values(status=target)
    )
    await session.commit()
    if result.rowcount != 1:
        return None
    await session.refresh(order)
    return order


# ---------- admins ----------
def setup_code_is_safe() -> bool:
    return len(settings.OWNER_SETUP_CODE or "") >= MIN_SETUP_CODE_LENGTH


async def is_admin(session: AsyncSession, user_id: int) -> bool:
    return await session.get(Admin, user_id) is not None


async def is_owner(session: AsyncSession, user_id: int) -> bool:
    admin = await session.get(Admin, user_id)
    return admin is not None and admin.role == "owner"


async def claim_ownership(session: AsyncSession, code: str, user_id: int, name: str) -> str:
    """'claimed' | 'already_owner' | 'invalid'. The setup code works only while the shop has no owner."""
    me = await session.get(Admin, user_id)
    if me and me.role == "owner":
        return "already_owner"
    owner_exists = await session.scalar(select(Admin.telegram_id).where(Admin.role == "owner").limit(1))
    code_ok = setup_code_is_safe() and hmac.compare_digest(
        code.strip().encode("utf-8"), settings.OWNER_SETUP_CODE.encode("utf-8")
    )
    if owner_exists is not None or not code_ok:
        return "invalid"
    if me:
        me.role = "owner"
    else:
        session.add(Admin(telegram_id=user_id, name=name, role="owner"))
    await session.commit()
    return "claimed"


# ---------- stats ----------
async def shop_stats(session: AsyncSession) -> dict[str, int]:
    by_status = dict((await session.execute(select(Order.status, func.count(Order.id)).group_by(Order.status))).all())
    revenue = await session.scalar(
        select(func.coalesce(func.sum(Order.total), 0)).where(Order.status.notin_(["new", "cancelled"]))
    )
    return {
        "users": int(await session.scalar(select(func.count(User.telegram_id))) or 0),
        "products": int(await session.scalar(select(func.count(Product.id))) or 0),
        "in_stock": int(await session.scalar(select(func.count(Product.id)).where(Product.in_stock.is_(True))) or 0),
        "revenue": int(revenue or 0),
        **{f"orders_{status}": int(count) for status, count in by_status.items()},
    }
