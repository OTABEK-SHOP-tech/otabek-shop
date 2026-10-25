import os
import uuid
from pathlib import Path
from typing import Any, List, Optional
from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, Header, HTTPException, UploadFile, status
from sqlalchemy import select, delete, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from bekstyle.api.auth import TelegramUser, get_current_user
from bekstyle.api.schemas import OrderCreate, OrderOut, format_som
from bekstyle.config import settings
from bekstyle.db import CartItem, Order, Product, get_db, utcnow, is_demo_product
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
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
):
    if idempotency_key is not None:
        idempotency_key = idempotency_key.strip()
        if not idempotency_key or len(idempotency_key) > 128:
            raise HTTPException(status_code=400, detail="Idempotency-Key noto'g'ri")
        existing = await db.scalar(select(Order).where(Order.user_id == user.id, Order.idempotency_key == idempotency_key))
        if existing:
            return to_order_out(existing)
    name = payload.customer_name.strip()
    digits = "".join(c for c in payload.phone if c.isdigit())
    if not name or len(name) > 255 or len(payload.address.strip()) < 3 or len(payload.address) > 255:
        raise HTTPException(status_code=400, detail="Ism va yetkazish manzilini to‘liq kiriting")
    if len(digits) != 12 or not digits.startswith("998"):
        raise HTTPException(status_code=400, detail="Telefon raqamini +998 bilan to‘liq kiriting")

    def snapshot(prod: Product | None, color: str | None, size: str | None, qty: int) -> dict[str, Any]:
        if not prod or not prod.in_stock or prod.price <= 0:
            raise HTTPException(status_code=409, detail="Mahsulot hozir mavjud emas")
        if is_demo_product(prod):
            raise HTTPException(status_code=409, detail="Bu namuna mahsuloti. Haqiqiy mahsulotlar tez orada qo‘shiladi.")
        if qty < 1 or qty > 99:
            raise HTTPException(status_code=400, detail="Mahsulot soni 1 dan 99 gacha bo‘lsin")
        if (prod.colors and color not in prod.colors) or (not prod.colors and color):
            raise HTTPException(status_code=409, detail="Mahsulot rangini qayta tanlang")
        if (prod.sizes and size not in prod.sizes) or (not prod.sizes and size):
            raise HTTPException(status_code=409, detail="Mahsulot o‘lchamini qayta tanlang")
        return {"product_id": prod.id, "title": prod.title, "price": prod.price,
                "color": color or "", "size": size or "", "qty": qty,
                "photo": prod.photos[0] if prod.photos else ""}

    cart_items = (await db.execute(select(CartItem).where(CartItem.user_id == user.id))).scalars().all()
    items_snapshot: List[dict[str, Any]] = []
    if cart_items:
        for item in cart_items:
            items_snapshot.append(snapshot(item.product, item.color, item.size, item.qty))
    elif payload.items:
        for item in payload.items:
            prod = await db.get(Product, item.product_id)
            items_snapshot.append(snapshot(prod, item.color, item.size, item.qty))
    total = sum(item["price"] * item["qty"] for item in items_snapshot)

    if not items_snapshot:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Savat bo'sh, buyurtma berish uchun mahsulot tanlang",
        )

    full_address = f"{payload.city}, {payload.address}".strip(" ,")
    new_order = Order(
        user_id=user.id,
        customer_name=name,
        customer_username=user.username,
        phone="+" + digits,
        city=payload.city.strip(),
        address=full_address,
        items=items_snapshot,
        total=total,
        status="pending_payment",  # Initial state: awaiting payment
        cargo_status="pending",
        idempotency_key=idempotency_key,
    )
    db.add(new_order)
    try:
        await db.flush()
        await db.execute(delete(CartItem).where(CartItem.user_id == user.id))
        await db.commit()
    except IntegrityError:
        await db.rollback()
        if idempotency_key:
            existing = await db.scalar(select(Order).where(Order.user_id == user.id, Order.idempotency_key == idempotency_key))
            if existing:
                return to_order_out(existing)
        raise HTTPException(status_code=409, detail="Buyurtma yangilanmoqda. Qayta urinib ko‘ring")
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
    order = await db.scalar(select(Order).where(Order.id == order_id).with_for_update())
    if not order:
        raise HTTPException(status_code=404, detail="Buyurtma topilmadi")
    if order.user_id != user.id and not user.is_admin:
        raise HTTPException(status_code=403, detail="Ruxsat berilmagan")
    if order.status not in {"pending_payment", "payment_rejected"}:
        raise HTTPException(status_code=409, detail="Bu buyurtma uchun yangi chek qabul qilinmaydi")

    # Only expose/use the two configured recipient cards.  A client cannot
    # inject an arbitrary card label into the order record.
    from bekstyle.db import get_setting
    configured_cards = {
        (await get_setting(db, "payment_card_1") or "").strip(),
        (await get_setting(db, "payment_card_2") or "").strip(),
    }
    selected = selected_card.strip()
    if selected not in configured_cards or not selected:
        raise HTTPException(status_code=400, detail="To'lov kartasi noto'g'ri")

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

    # Keep uploads bounded so a client cannot exhaust the receipt volume.
    max_bytes = 10 * 1024 * 1024
    size = 0
    with open(dest_path, "wb") as buffer:
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            if size > max_bytes:
                dest_path.unlink(missing_ok=True)
                raise HTTPException(status_code=413, detail="Chek hajmi 10 MB dan oshmasin")
            buffer.write(chunk)

    receipt_data = dest_path.read_bytes()
    mime = None
    if receipt_data.startswith(b"\x89PNG\r\n\x1a\n") and ext == ".png":
        mime = "image/png"
    elif receipt_data.startswith(b"\xff\xd8\xff") and ext in {".jpg", ".jpeg"}:
        mime = "image/jpeg"
    elif receipt_data[:4] == b"RIFF" and receipt_data[8:12] == b"WEBP" and ext == ".webp":
        mime = "image/webp"
    elif receipt_data.startswith(b"%PDF-") and ext == ".pdf":
        mime = "application/pdf"
    if not mime:
        dest_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="Yaroqli rasm yoki PDF chek faylini tanlang")
    order.selected_card = selected
    order.receipt_url = f"/api/media/receipts/{clean_filename}"
    order.receipt_bytes = receipt_data
    order.receipt_content_type = mime
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
    order = await db.scalar(select(Order).where(Order.id == order_id).with_for_update())
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
    order = await db.scalar(select(Order).where(Order.id == order_id).with_for_update())
    if not order:
        raise HTTPException(status_code=404, detail="Buyurtma topilmadi")
    if order.status != "payment_review":
        raise HTTPException(status_code=409, detail="Buyurtma to‘lov tekshiruvida emas")
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
    order = await db.scalar(select(Order).where(Order.id == order_id).with_for_update())
    if not order:
        raise HTTPException(status_code=404, detail="Buyurtma topilmadi")
    if order.status != "payment_review":
        raise HTTPException(status_code=409, detail="Buyurtma to'lov tekshiruvida emas")
    order.status = "payment_rejected"
    order.reject_reason = reason
    await db.commit()
    await db.refresh(order)
    return to_order_out(order)
