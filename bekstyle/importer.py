"""Bulk importer engine for BEK STYLE: imports 100 curated streetwear products and configures Ali Brand Kargo."""

import asyncio
import logging
from typing import Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bekstyle.streetwear_100 import STREETWEAR_100_PRODUCTS
from bekstyle.db import (
    Category,
    Product,
    Setting,
    async_session,
    seed_categories,
)

logger = logging.getLogger("bekstyle.importer")

ALI_CARGO_CARRIER = "Ali brand kargo"
ALI_CARGO_INFO = (
    "Kargo: Ali brand kargo\n"
    "Tarif: 100gr — 12 000 so'm, 150gr — 24 000 so'm\n"
    "Ali brand kargo dan olib kelinadi. Kargo haqi tovar yetib kelgach tortilib alohida hisoblanadi."
)


async def update_cargo_settings(session: AsyncSession) -> None:
    settings_to_update = {
        "cargo_carrier": ALI_CARGO_CARRIER,
        "cargo_info": ALI_CARGO_INFO,
    }
    for k, v in settings_to_update.items():
        row = await session.get(Setting, k)
        if row:
            row.value = v
        else:
            session.add(Setting(key=k, value=v))
    await session.commit()
    logger.info("Ali brand kargo settings successfully updated in database.")


async def import_100_products(session: AsyncSession) -> dict[str, Any]:
    cat_map = await seed_categories(session)
    inserted_count = 0
    updated_count = 0

    # Clean up old demo products if any exist
    from bekstyle.db import DEFAULT_PRODUCTS, is_demo_product
    old_demo_titles = {item["title"] for item in DEFAULT_PRODUCTS}
    demo_prods = (await session.execute(select(Product).where(Product.title.in_(old_demo_titles)))).scalars().all()
    for dp in demo_prods:
        if is_demo_product(dp):
            await session.delete(dp)
    await session.flush()

    for item in STREETWEAR_100_PRODUCTS:
        cat_id = cat_map.get(item["category_name"])
        if not cat_id:
            # Fallback or create category if missing
            res = await session.execute(select(Category).where(Category.name == item["category_name"]))
            cat = res.scalars().first()
            if not cat:
                cat = Category(name=item["category_name"], emoji="👕", sort_order=50)
                session.add(cat)
                await session.flush()
            cat_id = cat.id
            cat_map[item["category_name"]] = cat_id

        # Check existing product by title
        res = await session.execute(select(Product).where(Product.title == item["title"]))
        prod = res.scalars().first()

        if not prod:
            prod = Product(
                title=item["title"],
                description=item["description"],
                price=item["price"],
                old_price=item.get("old_price"),
                category_id=cat_id,
                photos=item["photos"],
                colors=item["colors"],
                sizes=item["sizes"],
                is_new=item.get("is_new", True),
                is_hit=item.get("is_hit", False),
                in_stock=True,
            )
            session.add(prod)
            inserted_count += 1
        else:
            prod.description = item["description"]
            prod.price = item["price"]
            prod.old_price = item.get("old_price")
            prod.category_id = cat_id
            prod.photos = item["photos"]
            prod.colors = item["colors"]
            prod.sizes = item["sizes"]
            prod.is_new = item.get("is_new", True)
            prod.is_hit = item.get("is_hit", False)
            prod.in_stock = True
            updated_count += 1

    await session.commit()
    await update_cargo_settings(session)

    total_prods = (await session.execute(select(Product.id))).scalars().all()

    result = {
        "status": "success",
        "inserted": inserted_count,
        "updated": updated_count,
        "total_in_batch": len(STREETWEAR_100_PRODUCTS),
        "total_in_db": len(total_prods),
        "cargo_carrier": ALI_CARGO_CARRIER,
    }
    logger.info("Bulk import completed: %s", result)
    return result


async def main():
    logging.basicConfig(level=logging.INFO)
    print("Starting 100 Streetwear bulk import to Neon PostgreSQL...")
    async with async_session() as session:
        res = await import_100_products(session)
        print(f"Result: {res}")


if __name__ == "__main__":
    asyncio.run(main())
