from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy import select, delete, desc, update, or_
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import get_current_user, TelegramUser
from api.schemas import OrderCreate, OrderOut, UserMeOut
from api.services.formatters import format_price, calculate_cargo, format_cargo_stage
from bot.services.order_notifier import send_payment_instructions
from bot.services.referral_service import validate_and_calculate_coupon_discount
from db.models import Order, CartItem, Product, Setting, User, ReferralCoupon, PromoCode, utcnow
from db.session import get_db

router = APIRouter(prefix="/orders", tags=["orders"])


@router.get("/me/cashback", response_model=UserMeOut)
async def get_my_cashback(
    user: TelegramUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    res = await db.execute(select(User).where(User.telegram_id == user.id))
    db_user = res.scalars().first()
    bal = db_user.cashback_balance if db_user else 0
    name = db_user.name if db_user else user.first_name
    return UserMeOut(
        telegram_id=user.id,
        name=name,
        username=user.username,
        cashback_balance=bal,
        formatted_cashback_balance=format_price(bal),
        max_order_cashback_percent=20,
    )


@router.post("", response_model=OrderOut)
async def create_order(
    payload: OrderCreate,
    background_tasks: BackgroundTasks,
    user: TelegramUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Retrieve current cart items
    res_cart = await db.execute(select(CartItem).where(CartItem.user_id == user.id))
    cart_items = res_cart.scalars().all()

    if not cart_items and not payload.items:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Savat bo'sh, buyurtma berish uchun mahsulot tanlang"
        )

    # Get cargo rate
    res_rate = await db.execute(select(Setting).where(Setting.key == "cargo_rate"))
    rate_setting = res_rate.scalars().first()
    cargo_rate = int(rate_setting.value) if rate_setting and rate_setting.value.isdigit() else 12000

    items_snapshot = []
    total = 0
    total_weight = 0

    if cart_items:
        for item in cart_items:
            prod = item.product
            if not prod:
                continue
            item_subtotal = prod.price * item.qty
            total += item_subtotal
            if prod.weight_grams:
                total_weight += prod.weight_grams * item.qty

            photo = prod.photos[0] if prod.photos and len(prod.photos) > 0 else ""
            items_snapshot.append({
                "product_id": prod.id,
                "title": prod.title,
                "price": prod.price,
                "size": item.size,
                "color": item.color,
                "qty": item.qty,
                "weight_grams": prod.weight_grams,
                "photo": photo,
            })
    elif payload.items:
        for it in payload.items:
            qty = int(it.get("qty", 1))
            if qty < 1:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Mahsulot soni kamida 1 ta bo'lishi kerak",
                )
            pid = it.get("product_id")
            db_prod = None
            if pid is not None:
                p_res = await db.execute(select(Product).where(Product.id == int(pid)))
                db_prod = p_res.scalars().first()
            if db_prod:
                unit_price = db_prod.price
                item_title = db_prod.title
                item_weight = db_prod.weight_grams
                item_photo = db_prod.photos[0] if db_prod.photos else (it.get("photo") or "")
            else:
                unit_price = int(it.get("price", 0))
                if unit_price < 0:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Mahsulot narxi manfiy bo'lishi mumkin emas",
                    )
                item_title = it.get("title") or it.get("product_title") or "Mahsulot"
                item_weight = it.get("weight_grams")
                item_photo = it.get("photo") or ""

            total += unit_price * qty
            if item_weight:
                total_weight += int(item_weight) * qty
            items_snapshot.append({
                "product_id": pid,
                "title": item_title,
                "price": unit_price,
                "size": it.get("size"),
                "color": it.get("color"),
                "qty": qty,
                "weight_grams": item_weight,
                "photo": item_photo,
            })

    # Apply 20% coupon discount if provided
    discount_amount = 0
    applied_coupon_code = None
    applied_coupon_obj = None

    if payload.coupon_code:
        clean_code = payload.coupon_code.strip().upper()
        val_res = await validate_and_calculate_coupon_discount(
            session=db,
            user_id=user.id,
            code=clean_code,
            cart_items=items_snapshot,
            selected_product_id=payload.coupon_product_id,
        )
        if not val_res.get("valid"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=val_res.get("message", "Kupon yaroqsiz"),
            )

        discount_amount = val_res["discount_amount"]
        applied_coupon_code = clean_code

        rc_res = await db.execute(select(ReferralCoupon).where(ReferralCoupon.code == clean_code))
        applied_coupon_obj = rc_res.scalars().first()

    subtotal_after_discount = max(0, total - discount_amount)

    # Apply cashback if requested (max 20% of subtotal_after_discount)
    res_user = await db.execute(select(User).where(User.telegram_id == user.id))
    db_user = res_user.scalars().first()
    user_cashback = db_user.cashback_balance if db_user else 0

    applied_cashback = 0
    if payload.use_cashback and payload.use_cashback > 0:
        max_allowed = int(subtotal_after_discount * 0.20)
        applied_cashback = min(payload.use_cashback, user_cashback, max_allowed)
        if applied_cashback > 0 and db_user:
            cb_res = await db.execute(
                update(User)
                .where(
                    User.telegram_id == user.id,
                    User.cashback_balance >= applied_cashback,
                )
                .values(cashback_balance=User.cashback_balance - applied_cashback)
            )
            if cb_res.rowcount == 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Keshbek balansi yetarli emas ❌",
                )

    final_total = max(0, subtotal_after_discount - applied_cashback)

    estimated_cargo = calculate_cargo(total_weight, cargo_rate)

    customer_name = payload.customer_name or f"{user.first_name} {user.last_name or ''}".strip() or "Mijoz"
    customer_username = payload.customer_username or user.username

    new_order = Order(
        user_id=user.id,
        customer_name=customer_name,
        customer_username=customer_username,
        items_snapshot=items_snapshot,
        total=final_total,
        estimated_cargo=estimated_cargo,
        status="awaiting_receipt",
        receipt_photo_id=None,
        promo_code=applied_coupon_code,
        discount_amount=discount_amount,
        cashback_used=applied_cashback,
        cargo_stage="china_warehouse",
    )
    db.add(new_order)
    await db.flush()

    if applied_coupon_obj:
        # Atomic update on ReferralCoupon to prevent double-spending under concurrent checkouts
        stmt_rc = (
            update(ReferralCoupon)
            .where(
                ReferralCoupon.id == applied_coupon_obj.id,
                ReferralCoupon.is_used == False,
            )
            .values(
                is_used=True,
                used_at=utcnow(),
                order_id=new_order.id,
                product_id=val_res.get("product_id"),
                discount_amount=discount_amount,
            )
        )
        rc_update_res = await db.execute(stmt_rc)
        if rc_update_res.rowcount == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ushbu kupon allaqachon ishlatilgan yoki ayni paytda band ❌",
            )

        # Also update PromoCode table if present
        pr_res = await db.execute(select(PromoCode).where(PromoCode.code == applied_coupon_code))
        promo_obj = pr_res.scalars().first()
        if promo_obj:
            promo_obj.used_count += 1
            if promo_obj.max_uses and promo_obj.used_count >= promo_obj.max_uses:
                promo_obj.is_active = False
    elif applied_coupon_code:
        # Atomic promo code redemption update to avoid race conditions
        pr_update = await db.execute(
            update(PromoCode)
            .where(
                PromoCode.code == applied_coupon_code,
                PromoCode.is_active == True,
                or_(
                    PromoCode.max_uses.is_(None),
                    PromoCode.max_uses == 0,
                    PromoCode.used_count < PromoCode.max_uses,
                ),
            )
            .values(used_count=PromoCode.used_count + 1)
        )
        if pr_update.rowcount == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Kupondan foydalanish limiti tugagan ❌",
            )
        pr_res = await db.execute(select(PromoCode).where(PromoCode.code == applied_coupon_code))
        promo_obj = pr_res.scalars().first()
        if promo_obj and promo_obj.max_uses and promo_obj.used_count >= promo_obj.max_uses:
            promo_obj.is_active = False

    # Clear user's cart
    await db.execute(delete(CartItem).where(CartItem.user_id == user.id))
    await db.commit()
    await db.refresh(new_order)

    # Trigger background Telegram notification (payment instructions to customer only)
    background_tasks.add_task(
        send_payment_instructions,
        order_id=new_order.id,
        user_id=user.id,
        customer_name=customer_name,
        customer_username=customer_username,
        items=items_snapshot,
        total=final_total,
        estimated_cargo=estimated_cargo,
    )

    return OrderOut(
        id=new_order.id,
        user_id=new_order.user_id,
        customer_name=new_order.customer_name,
        customer_username=new_order.customer_username,
        items_snapshot=new_order.items_snapshot,
        total=new_order.total,
        formatted_total=format_price(new_order.total),
        estimated_cargo=new_order.estimated_cargo,
        formatted_cargo=format_price(new_order.estimated_cargo),
        status=new_order.status,
        receipt_photo_id=new_order.receipt_photo_id,
        promo_code=new_order.promo_code,
        discount_amount=new_order.discount_amount,
        formatted_discount_amount=format_price(new_order.discount_amount) if new_order.discount_amount else "",
        cashback_used=new_order.cashback_used,
        formatted_cashback_used=format_price(new_order.cashback_used),
        cargo_stage=new_order.cargo_stage,
        formatted_cargo_stage=format_cargo_stage(new_order.cargo_stage),
        created_at=new_order.created_at,
    )


@router.get("", response_model=List[OrderOut])
async def list_user_orders(
    user: TelegramUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    res = await db.execute(
        select(Order).where(Order.user_id == user.id).order_by(desc(Order.created_at))
    )
    orders = res.scalars().all()
    return [
        OrderOut(
            id=o.id,
            user_id=o.user_id,
            customer_name=o.customer_name,
            customer_username=o.customer_username,
            items_snapshot=o.items_snapshot,
            total=o.total,
            formatted_total=format_price(o.total),
            estimated_cargo=o.estimated_cargo,
            formatted_cargo=format_price(o.estimated_cargo),
            status=o.status,
            receipt_photo_id=o.receipt_photo_id,
            promo_code=o.promo_code,
            discount_amount=o.discount_amount,
            formatted_discount_amount=format_price(o.discount_amount) if o.discount_amount else "",
            cashback_used=o.cashback_used,
            formatted_cashback_used=format_price(o.cashback_used),
            cargo_stage=o.cargo_stage,
            formatted_cargo_stage=format_cargo_stage(o.cargo_stage),
            created_at=o.created_at,
        )
        for o in orders
    ]
