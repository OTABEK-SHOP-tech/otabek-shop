import json
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import select, text

from bekstyle.catalog_import import validate_manifest
from bekstyle.db import Category, Product, async_session, engine
from bekstyle.import_catalog import apply_plans, public_product_data


def doc():
    return {"products": [{"source_url": "https://mobile.yangkeduo.com/goods.html?goods_id=7", "source_product_id": "7", "verified": True, "checked_at": datetime.now(timezone.utc).isoformat(), "title": "Shim", "category": "Shimlar", "photos": ["https://img.pddpic.com/x.jpg"], "costs": {"yuan_rate": 1850, "china_shipping_cny": 1, "intermediary_fee_som": 1000, "other_costs_som": 0}, "target_profit_som": 10000, "variants": [{"sku_id": "a", "color": "Qora", "size": "M", "cost_cny": 20, "in_stock": True}, {"sku_id": "b", "color": "Oq", "size": "L", "cost_cny": 30, "in_stock": False}]}]}


@pytest.mark.usefixtures("db")
async def test_apply_is_idempotent_and_uses_max_cost():
    plans = validate_manifest(doc())
    assert public_product_data(plans[0])["price"] == 69000
    assert await apply_plans(plans) == 1
    assert await apply_plans(plans) == 1
    async with async_session() as session:
        rows = (await session.scalars(select(Product).where(Product.source_key == "pdd:7"))).all()
        assert len(rows) == 1
        assert rows[0].cost_cny == 30
        assert rows[0].colors == ["Qora"] and rows[0].sizes == ["M"]
        assert rows[0].source_details["variants"][1]["in_stock"] is False


@pytest.mark.usefixtures("db")
async def test_public_data_has_no_private_decimal_objects():
    plan = validate_manifest(doc())[0]
    payload = public_product_data(plan)
    json.dumps(payload)
    assert "cost_cny" not in payload and "source_url" not in payload


@pytest.mark.usefixtures("db")
async def test_legacy_products_table_migration_preserves_private_json():
    """Exercise additive migration against a table from before source tracking."""
    from bekstyle.db import migrate_columns

    async with engine.begin() as conn:
        await conn.execute(text("DROP INDEX IF EXISTS uq_products_source_key"))
        await conn.execute(text("ALTER TABLE products DROP COLUMN source_key"))
        await conn.execute(text("ALTER TABLE products DROP COLUMN source_details"))
    await migrate_columns()
    await migrate_columns()
    async with async_session() as session:
        category = (await session.scalars(select(Category))).first()
        product = Product(
            title="Legacy import", description="Pre-order", price=69000,
            cost_cny=Decimal("30"), category_id=category.id,
            photos=["https://img.pddpic.com/x.jpg"], colors=["Qora"], sizes=["M"],
            source_key="pdd:legacy-1",
            source_details={"cost_inputs": {"yuan_rate": "1850"}, "variants": [{"cost_cny": "30"}]},
        )
        session.add(product)
        await session.commit()
        loaded = await session.scalar(select(Product).where(Product.source_key == "pdd:legacy-1"))
        assert loaded.source_details["cost_inputs"]["yuan_rate"] == "1850"
        assert loaded.source_details["variants"][0]["cost_cny"] == "30"
