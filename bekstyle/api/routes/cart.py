from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from bekstyle.api.auth import TelegramUser, get_current_user
from bekstyle.api.schemas import (
    CartItemAdd,
    CartItemOut,
    CartItemUpdate,
    CartSummaryOut,
    format_som,
)
from bekstyle.db import CartItem, Product, get_db
from bekstyle.services import is_product_variant_available

router = APIRouter(prefix="/cart", tags=["cart"])


async def compute_cart_summary(user_id: int, db: AsyncSession) -> CartSummaryOut:
    stmt = select(CartItem).where(CartItem.user_id == user_id)
    res = await db.execute(stmt)
    cart_items = res.scalars().all()

    items_out: List[CartItemOut] = []
    subtotal = 0
    total_qty = 0

    for item in cart_items:
        prod = item.product
        if not prod:
            continue
        item_total = prod.price * item.qty
        subtotal += item_total
        total_qty += item.qty

        photo = prod.photos[0] if prod.photos else None
        items_out.append(
            CartItemOut(
                id=item.id,
                product_id=prod.id,
                product_title=prod.title,
                product_price=prod.price,
                formatted_price=format_som(prod.price),
                product_photo=photo,
                color=item.color,
                size=item.size,
                qty=item.qty,
                item_total=item_total,
                formatted_item_total=format_som(item_total),
            )
        )

    return CartSummaryOut(
        items=items_out,
        total_items=total_qty,
        subtotal=subtotal,
        formatted_subtotal=format_som(subtotal),
        grand_total=subtotal,
        formatted_grand_total=format_som(subtotal),
    )


@router.get("", response_model=CartSummaryOut)
async def get_cart(
    user: TelegramUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await compute_cart_summary(user.id, db)


@router.post("", response_model=CartSummaryOut)
async def add_to_cart(
    payload: CartItemAdd,
    user: TelegramUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    prod = await db.get(Product, payload.product_id)
    if not prod or not prod.in_stock:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mahsulot mavjud emas")
    if not is_product_variant_available(prod, payload.color, payload.size):
        raise HTTPException(status_code=409, detail="Bu rang va o‘lcham hozir mavjud emas. Qayta tanlang.")
    if payload.qty < 1 or payload.qty > 99:
        raise HTTPException(status_code=400, detail="Mahsulot soni 1 dan 99 gacha bo‘lsin")

    stmt = select(CartItem).where(
        CartItem.user_id == user.id,
        CartItem.product_id == payload.product_id,
        CartItem.color == payload.color,
        CartItem.size == payload.size,
    )
    existing = (await db.execute(stmt)).scalars().first()
    if existing:
        if existing.qty + payload.qty > 99:
            raise HTTPException(status_code=400, detail="Mahsulot soni 99 tadan oshmasin")
        existing.qty += payload.qty
    else:
        new_item = CartItem(
            user_id=user.id,
            product_id=payload.product_id,
            color=payload.color,
            size=payload.size,
            qty=payload.qty,
        )
        db.add(new_item)

    await db.commit()
    return await compute_cart_summary(user.id, db)


@router.patch("/{item_id}", response_model=CartSummaryOut)
async def update_cart_qty(
    item_id: int,
    payload: CartItemUpdate,
    user: TelegramUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(CartItem).where(CartItem.id == item_id, CartItem.user_id == user.id)
    item = (await db.execute(stmt)).scalars().first()
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Element topilmadi")

    if payload.qty > 99:
        raise HTTPException(status_code=400, detail="Mahsulot soni 99 tadan oshmasin")
    if payload.qty <= 0:
        await db.delete(item)
    else:
        item.qty = payload.qty

    await db.commit()
    return await compute_cart_summary(user.id, db)


@router.delete("/{item_id}", response_model=CartSummaryOut)
async def remove_cart_item(
    item_id: int,
    user: TelegramUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(CartItem).where(CartItem.id == item_id, CartItem.user_id == user.id)
    item = (await db.execute(stmt)).scalars().first()
    if item:
        await db.delete(item)
        await db.commit()
    return await compute_cart_summary(user.id, db)


@router.delete("", response_model=CartSummaryOut)
async def clear_cart(
    user: TelegramUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await db.execute(delete(CartItem).where(CartItem.user_id == user.id))
    await db.commit()
    return await compute_cart_summary(user.id, db)
