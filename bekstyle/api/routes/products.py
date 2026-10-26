from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, or_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from bekstyle.api.schemas import ProductOut, format_som
from bekstyle.db import Category, Product, get_db, is_demo_product, DEFAULT_PRODUCTS
from bekstyle.services import available_source_variants

router = APIRouter(prefix="/products", tags=["products"])


def to_product_out(p: Product) -> ProductOut:
    demo = is_demo_product(p)
    demo_names = ["Keng bichimli hudi", "Ko‘p cho‘ntakli shim", "Keng bichimli futbolka", "Keng jinsi shim", "Bomber kurtka", "Qalin taglikli krossovka", "Kundalik yelka sumkasi", "Keng bichimli svitshot"]
    titles = {item["title"]: demo_names[i] for i, item in enumerate(DEFAULT_PRODUCTS)}
    title = titles.get(p.title, p.title) if demo else p.title
    disc = None
    if not demo and p.old_price and p.old_price > p.price:
        disc = int(round((p.old_price - p.price) / p.old_price * 100))

    cat_name = p.category.name if p.category else ""
    variants = available_source_variants(p)
    return ProductOut(
        id=p.id,
        title=title,
        name=title,
        description=("Ko‘rinishni sinab ko‘rish uchun namuna. Haqiqiy mahsulotlar alohida qo‘shiladi." if demo else (p.description or "")),
        price=p.price,
        formatted_price=format_som(p.price),
        old_price=None if demo else p.old_price,
        formatted_old_price=format_som(p.old_price) if p.old_price and not demo else None,
        discount_percent=disc,
        category_id=p.category_id,
        category_name=cat_name,
        photos=p.photos or [],
        colors=list(dict.fromkeys(v["color"] for v in variants if v["color"] is not None)) if variants is not None else (p.colors or []),
        sizes=list(dict.fromkeys(v["size"] for v in variants if v["size"] is not None)) if variants is not None else (p.sizes or []),
        available_variants=variants,
        in_stock=p.in_stock,
        is_new=p.is_new,
        is_hit=p.is_hit,
        views=p.views or 0,
        is_demo=demo,
    )


@router.get("", response_model=List[ProductOut])
async def list_products(
    category_id: Optional[int] = Query(None),
    search: Optional[str] = Query(None),
    sort: Optional[str] = Query("newest"),  # newest, price_asc, price_desc
    size: Optional[str] = Query(None),
    is_hit: Optional[bool] = Query(None),
    is_new: Optional[bool] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Product).where(Product.in_stock == True)  # noqa: E712

    if category_id:
        stmt = stmt.where(Product.category_id == category_id)

    if is_hit is not None:
        stmt = stmt.where(Product.is_hit == is_hit)

    if is_new is not None:
        stmt = stmt.where(Product.is_new == is_new)

    if search:
        pattern = f"%{search.strip().lower()}%"
        stmt = stmt.where(
            or_(
                Product.title.ilike(pattern),
                Product.description.ilike(pattern),
            )
        )

    if sort == "price_asc":
        stmt = stmt.order_by(Product.price.asc())
    elif sort == "price_desc":
        stmt = stmt.order_by(Product.price.desc())
    else:
        stmt = stmt.order_by(desc(Product.id))

    res = await db.execute(stmt)
    products = res.scalars().all()

    # Filter size if requested
    if size:
        sz_clean = size.strip().upper()
        products = [p for p in products if any(s.strip().upper() == sz_clean for s in to_product_out(p).sizes)]

    return [to_product_out(p) for p in products]


@router.get("/{product_id}", response_model=ProductOut)
async def get_product_detail(product_id: int, db: AsyncSession = Depends(get_db)):
    p = await db.get(Product, product_id)
    if not p:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mahsulot topilmadi")

    # Increment views
    p.views = (p.views or 0) + 1
    await db.commit()

    return to_product_out(p)
