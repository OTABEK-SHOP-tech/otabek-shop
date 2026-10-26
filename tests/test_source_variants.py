import pytest

from bekstyle.db import Product, async_session
from bekstyle.services import (
    add_to_cart,
    available_source_variants,
    create_order_from_cart,
    is_product_variant_available,
)


def source_product(**details) -> Product:
    return Product(
        title="Source", price=100_000, category_id=1, in_stock=True,
        source_key="pdd:1", source_details=details,
    )


def test_source_variants_are_available_pairs_only() -> None:
    p = source_product(variants=[
        {"color": "Black", "size": "M", "in_stock": True, "cost_cny": 10},
        {"color": "Black", "size": "L", "in_stock": False},
        {"color": "White", "size": "M", "in_stock": True},
        {"color": "Black", "size": "M", "in_stock": True},
    ])
    assert available_source_variants(p) == [{"color": "Black", "size": "M"}, {"color": "White", "size": "M"}]
    assert is_product_variant_available(p, "Black", "M")
    assert not is_product_variant_available(p, "Black", "L")
    assert not is_product_variant_available(p, "White", "L")


def test_malformed_source_fails_closed() -> None:
    p = source_product(variants=[{"color": "Black", "size": "M", "in_stock": True}])
    p.source_details = {"bad": True}
    assert available_source_variants(p) == []
    assert not is_product_variant_available(p, "Black", "M")


def test_source_variant_can_have_absent_axes() -> None:
    p = source_product(variants=[
        {"color": None, "size": None, "in_stock": True},
        {"color": "Black", "size": None, "in_stock": True},
        {"color": "Black", "in_stock": True},
    ])
    assert available_source_variants(p) == [
        {"color": None, "size": None}, {"color": "Black", "size": None}
    ]
    assert is_product_variant_available(p, None, None)
    assert is_product_variant_available(p, "Black", None)
    assert not is_product_variant_available(p, "White", None)


@pytest.mark.usefixtures("db")
async def test_service_rejects_invalid_source_pair() -> None:
    async with async_session() as session:
        p = source_product(variants=[{"color": "Black", "size": "M", "in_stock": True}])
        session.add(p)
        await session.commit()
        with pytest.raises(ValueError):
            await add_to_cart(session, 991, p.id, "White", "M")
