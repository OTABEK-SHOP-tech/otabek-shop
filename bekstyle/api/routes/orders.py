from typing import Any, List
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import select, delete, desc
from sqlalchemy.ext.asyncio import AsyncSession

from bekstyle.api.auth import TelegramUser, get_current_user
from bekstyle.api.schemas import OrderCreate, OrderOut, format_som
from bekstyle.db import CartItem, Order, Product, get_db
from bekstyle.texts import ORDER_STATUSES

router = APIRouter(prefix="/orders", tags=["orders"])


def get_status_label(status_code: str) -> str:
    info = ORDER_STATUSES.get(status_code)
    return info[0] if info else status_code


def to_order_out(o: Order) -> OrderOut:
    return OrderOut(
        id=o.id,
        user_id=o.user_id,
        customer_name=o.customer_name,
        customer_username=o.customer_username,
        phone=o.phone,
        city=o.city or "",
        address=o.address,
        items=o.items or [],
        total=o.total,
        formatted_total=format_som(o.total),
        status=o.status,
        status_label=get_status_label(o.status),
        created_at=o.created_at,
    )


async def send_order_alert_bg(order_id: int):
    try:
        from bekstyle.api.server import bot_instance
        from bekstyle.db import async_session
        from bekstyle.notify import notify_admins_new_order

        if not bot_instance:
            return
        async with async_session() as session:
            order = await session.get(Order, order_id)
            if order:
                await notify_admins_new_order(bot_instance, order)
    except Exception as exc:
        import logging
        logging.getLogger("bekstyle").warning("Background order alert failed: %s", exc)


@router.post("", response_model=OrderOut)
async def create_order(
    payload: OrderCreate,
    background_tasks: BackgroundTasks,
    user: TelegramUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Retrieve current cart items or payload items
    stmt = select(CartItem).where(CartItem.user_id == user.id)
    cart_items = (await db.execute(stmt)).scalars().all()

    items_snapshot: List[dict[str, Any]] = []
    total = 0

    if cart_items:
        for it in cart_items:
            prod = it.product
            if not prod:
                continue
            item_subtotal = prod.price * it.qty
            total += item_subtotal
            photo = prod.photos[0] if prod.photos else ""
            items_snapshot.append({
                "product_id": prod.id,
                "title": prod.title,
                "price": prod.price,
                "color": it.color or "",
                "size": it.size or "",
                "qty": it.qty,
                "photo": photo,
            })
    elif payload.items:
        for it in payload.items:
            prod = await db.get(Product, it.product_id)
            price = prod.price if prod else it.price
            total += price * it.qty
            photo = (prod.photos[0] if prod and prod.photos else it.photo) or ""
            items_snapshot.append({
                "product_id": it.product_id,
                "title": it.title,
                "price": price,
                "color": it.color or "",
                "size": it.size or "",
                "qty": it.qty,
                "photo": photo,
            })

    if not items_snapshot:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Savat bo'sh, buyurtma berish uchun mahsulot tanlang",
        )

    full_address = f"{payload.city}, {payload.address}".strip(" ,")
    new_order = Order(
        user_id=user.id,
        customer_name=payload.customer_name.strip(),
        customer_username=payload.customer_username or user.username,
        phone=payload.phone.strip(),
        city=payload.city.strip(),
        address=full_address,
        items=items_snapshot,
        total=total,
        status="new",
    )
    db.add(new_order)
    await db.flush()

    # Clear user's cart
    await db.execute(delete(CartItem).where(CartItem.user_id == user.id))
    await db.commit()
    await db.refresh(new_order)

    # Notify admin via Telegram in background
    background_tasks.add_task(send_order_alert_bg, new_order.id)

    return to_order_out(new_order)


@router.get("/my", response_model=List[OrderOut])
async def list_my_orders(
    user: TelegramUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Order).where(Order.user_id == user.id).order_by(desc(Order.created_at))
    orders = (await db.execute(stmt)).scalars().all()
    return [to_order_out(o) for o in orders]
