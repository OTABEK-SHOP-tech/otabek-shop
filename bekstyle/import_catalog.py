"""Import a verified Pinduoduo manifest without scraping or notifications.

Default mode is a read-only dry run.  Pass ``--apply`` explicitly to write to
the configured database.
"""
from __future__ import annotations

import argparse
import asyncio
import json
from decimal import Decimal
from pathlib import Path
from typing import Any

from .catalog_import import ProductPlan, validate_manifest


def _json_decimal(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dict):
        return {k: _json_decimal(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_decimal(v) for v in value]
    return value


def load_manifest(path: str | Path) -> tuple[ProductPlan, ...]:
    with Path(path).open("r", encoding="utf-8") as handle:
        document = json.load(handle, parse_float=Decimal)
    return validate_manifest(document)


def public_product_data(plan: ProductPlan) -> dict[str, Any]:
    available = [v for v in plan.variants if v.in_stock]
    return {
        "title": plan.title,
        "category": plan.category,
        "photos": list(plan.photos),
        "colors": sorted({v.color for v in available if v.color is not None}),
        "sizes": sorted({v.size for v in available if v.size is not None}),
        "price": max(v.sale_price_som for v in plan.variants),
        "old_price": None,
        "in_stock": bool(available),
        "description": "Buyurtma asosida olib kelinadi. Kargo haqi alohida hisoblanadi.",
    }


def private_source_data(plan: ProductPlan) -> dict[str, Any]:
    return _json_decimal({
        "source_url": plan.source_url,
        "checked_at": plan.checked_at.isoformat(),
        "cost_inputs": plan.costs.__dict__,
        "target_profit_som": plan.variants[0].target_profit_som,
        "variants": [v.__dict__ for v in plan.variants],
    })


async def apply_plans(plans: tuple[ProductPlan, ...]) -> int:
    from sqlalchemy import select
    from .db import Category, Product, async_session, engine, migrate_columns
    from .db import Base

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await migrate_columns()
    async with async_session() as session:
        for plan in plans:
            category = await session.scalar(select(Category).where(Category.name == plan.category))
            if category is None:
                category = Category(name=plan.category, emoji="▫️")
                session.add(category)
                await session.flush()
            source_key = f"pdd:{plan.source_product_id}"
            product = await session.scalar(select(Product).where(Product.source_key == source_key))
            public = public_product_data(plan)
            values = dict(
                title=public["title"], description=public["description"], price=public["price"], old_price=None,
                cost_cny=max(v.cost_cny for v in plan.variants), category_id=category.id,
                photos=public["photos"], colors=public["colors"], sizes=public["sizes"],
                in_stock=public["in_stock"], source_key=source_key,
                source_details=private_source_data(plan),
            )
            if product is None:
                session.add(Product(**values))
            else:
                for key, value in values.items():
                    setattr(product, key, value)
        await session.commit()
    return len(plans)


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate or import a verified Pinduoduo manifest")
    parser.add_argument("manifest")
    parser.add_argument("--apply", action="store_true", help="write validated products to the configured database")
    args = parser.parse_args()
    try:
        plans = load_manifest(args.manifest)
        for plan in plans:
            preview = public_product_data(plan)
            print(f"- {plan.source_product_id}: {plan.title} · {preview['price']:,} so'm · {len(plan.variants)} SKU")
        if args.apply:
            count = asyncio.run(apply_plans(plans))
            print(f"Applied {count} product(s).")
        else:
            print(f"Dry run OK: {len(plans)} product(s); no database writes.")
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        parser.exit(2, f"Import manifest error: {exc}\n")


if __name__ == "__main__":
    main()
