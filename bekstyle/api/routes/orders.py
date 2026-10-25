import os
import shutil
import uuid
from pathlib import Path
from typing import Any, List, Optional
from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select, delete, desc
from sqlalchemy.ext.asyncio import AsyncSession

from bekstyle.api.auth import TelegramUser, get_current_user
from bekstyle.api.schemas import OrderCreate, OrderOut, format_som
from bekstyle.config import settings
from bekstyle.db import CartItem, Order, Product, get_db, utcnow
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
        selected_card=o.selected_card,
        receipt_url=o.receipt_url,
        receipt_uploaded_at=o.receipt_uploaded_at,
        reject_reason=o.reject_reason,
        cargo_price=o.cargo_price,
        formatted_cargo_price=format_som(o.cargo_price) if o.cargo_price is not None else None,
        cargo_status=o.cargo_status or "pending",
        cargo_weight=o.cargo_weight,
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


async def send_receipt_alert_bg(order_id: int, file_path: str):
    try:
        from bekstyle.api.server import bot_instance
        from bekstyle.db import async_session
        from bekstyle.notify import notify_admins_receipt_uploaded

        if not bot_instance:
            return
        async with async_session() as session:
            order = await session.get(Order, order_id)
            if order:
                await notify_admins_receipt_uploaded(bot_instance, order, file_path)
    except Exception as exc:
        import logging
        logging.getLogger("bekstyle").warning("Background receipt alert failed: %s", exc)


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
        status="pending_payment",  # Initial state: awaiting payment
        cargo_status="pending",
    )
    db.add(new_order)
    await db.flush()

    # Clear user's cart
    await db.execute(delete(CartItem).where(CartItem.user_id == user.id))
    await db.commit()
    await db.refresh(new_order)

    # Notify admin via Telegram in background about new order intent
    background_tasks.add_task(send_order_alert_bg, new_order.id)

    return to_order_out(new_order)


@router.post("/{order_id}/receipt", response_model=OrderOut)
async def upload_order_receipt(
    order_id: int,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    selected_card: str = Form(...),
    user: TelegramUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    order = await db.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Buyurtma topilmadi")
    if order.user_id != user.id and not user.is_admin:
        raise HTTPException(status_code=403, detail="Ruxsat berilmagan")

    # Validate extension
    filename = file.filename or "receipt.jpg"
    ext = Path(filename).suffix.lower()
    if ext not in [".jpg", ".jpeg", ".png", ".webp", ".pdf"]:
        raise HTTPException(
            status_code=400,
            detail="Faqat rasm (JPG, PNG, WEBP) yoki PDF formatdagi cheklar qabul qilinadi",
        )

    receipts_dir = Path(settings.DATA_DIR) / "receipts"
    receipts_dir.mkdir(parents=True, exist_ok=True)
    clean_filename = f"receipt_{order.id}_{uuid.uuid4().hex[:8]}{ext}"
    dest_path = receipts_dir / clean_filename

    with open(dest_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    order.selected_card = selected_card.strip()
    order.receipt_url = f"/api/media/receipts/{clean_filename}"
    order.receipt_uploaded_at = utcnow()
    order.status = "payment_review"
    order.reject_reason = None
    await db.commit()
    await db.refresh(order)

    # Background task to send admin notification with receipt
    background_tasks.add_task(send_receipt_alert_bg, order.id, str(dest_path))

    return to_order_out(order)


@router.get("/my", response_model=List[OrderOut])
async def list_my_orders(
    user: TelegramUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Order).where(Order.user_id == user.id).order_by(desc(Order.created_at))
    orders = (await db.execute(stmt)).scalars().all()
    return [to_order_out(o) for o in orders]


@router.get("/{order_id}", response_model=OrderOut)
async def get_order_by_id(
    order_id: int,
    user: TelegramUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    order = await db.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Buyurtma topilmadi")
    if order.user_id != user.id and not user.is_admin:
        raise HTTPException(status_code=403, detail="Ruxsat berilmagan")
    return to_order_out(order)


@router.post("/{order_id}/confirm-payment", response_model=OrderOut)
async def confirm_order_payment(
    order_id: int,
    background_tasks: BackgroundTasks,
    user: TelegramUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Faqat admin uchun")
    order = await db.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Buyurtma topilmadi")
    order.status = "paid"
    order.reject_reason = None
    await db.commit()
    await db.refresh(order)

    async def notify_customer():
        from bekstyle.api.server import bot_instance
        from bekstyle.notify import notify_customer_status
        if bot_instance:
            await notify_customer_status(bot_instance, order)

    background_tasks.add_task(notify_customer)
    return to_order_out(order)


@router.post("/{order_id}/reject-payment", response_model=OrderOut)
async def reject_order_payment(
    order_id: int,
    reason: str = Form("To'lov cheki yaroqsiz yoki mablag' kelib tushmadi"),
    user: TelegramUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Faqat admin uchun")
    order = await db.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Buyurtma topilmadi")
    order.status = "payment_rejected"
    order.reject_reason = reason
    await db.commit()
    await db.refresh(order)
    return to_order_out(order)
