from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from bekstyle.api.schemas import CategoryOut
from bekstyle.db import Category, Product, get_db

router = APIRouter(prefix="/categories", tags=["categories"])


@router.get("", response_model=List[CategoryOut])
async def list_categories(db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Category).order_by(Category.sort_order.asc(), Category.id.asc()))
    categories = res.scalars().all()

    result = []
    for c in categories:
        cnt_res = await db.execute(
            select(func.count(Product.id)).where(Product.category_id == c.id, Product.in_stock == True)
        )
        count = cnt_res.scalar() or 0
        result.append(
            CategoryOut(
                id=c.id,
                name=c.name,
                emoji=c.emoji,
                sort_order=c.sort_order,
                product_count=count,
            )
        )
    return result
