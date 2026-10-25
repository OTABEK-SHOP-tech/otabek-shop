import pytest
from sqlalchemy import select

from bekstyle.config import settings
from bekstyle.db import Admin, Category, Product, User, async_session
from bekstyle.services import (
    add_to_cart,
    cart_count,
    catalog_product_ids,
    change_order_status,
    claim_ownership,
    create_order_from_cart,
    get_cart,
)

CUSTOMER = 222


async def _product(title: str, price: int, in_stock: bool = True) -> int:
    async with async_session() as session:
        category_id = await session.scalar(select(Category.id).limit(1))
        product = Product(
            title=title,
            price=price,
            category_id=category_id,
            photos=["f1"],
            colors=["Qora"],
            sizes=["L"],
            in_stock=in_stock,
        )
        session.add(product)
        await session.commit()
        return product.id


@pytest.mark.usefixtures("db")
async def test_cart_merges_same_variant() -> None:
    pid = await _product("Hudi", 250_000)
    async with async_session() as session:
        await add_to_cart(session, CUSTOMER, pid, "Qora", "L")
        await add_to_cart(session, CUSTOMER, pid, "Qora", "L")
        count = await add_to_cart(session, CUSTOMER, pid, "Qora", None)
        items = await get_cart(session, CUSTOMER)
    assert count == 3
    assert {it.size: it.qty for it in items} == {"L": 2, None: 1}


@pytest.mark.usefixtures("db")
async def test_order_from_cart_snapshots_and_drops_sold_out() -> None:
    shirt = await _product("Futbolka", 189_000)
    sold_out = await _product("Kurtka", 450_000)
    async with async_session() as session:
        session.add(User(telegram_id=CUSTOMER, name="Aziz"))
        await session.commit()
        await add_to_cart(session, CUSTOMER, shirt, "Qora", "L")
        await add_to_cart(session, CUSTOMER, shirt, "Qora", "L")
        await add_to_cart(session, CUSTOMER, sold_out, "Qora", "L")
        product = await session.get(Product, sold_out)
        assert product is not None
        product.in_stock = False
        await session.commit()

        order, dropped = await create_order_from_cart(session, CUSTOMER, "Aziz", "aziz", "+998901234567", "Toshkent")
        assert order is not None
        assert dropped == 1
        assert order.total == 2 * 189_000
        assert order.items == [
            {"product_id": shirt, "title": "Futbolka", "price": 189_000, "color": "Qora", "size": "L", "qty": 2}
        ]
        assert order.created_at is not None
        assert await cart_count(session, CUSTOMER) == 0
        user = await session.get(User, CUSTOMER)
        assert user is not None and user.phone == "+998901234567"


@pytest.mark.usefixtures("db")
async def test_empty_cart_creates_no_order() -> None:
    async with async_session() as session:
        order, dropped = await create_order_from_cart(session, CUSTOMER, "Aziz", None, "+998", "Toshkent")
    assert order is None and dropped == 0


@pytest.mark.usefixtures("db")
async def test_status_changes_follow_flow_and_apply_once() -> None:
    pid = await _product("Shim", 300_000)
    async with async_session() as session:
        await add_to_cart(session, CUSTOMER, pid, "Qora", "L")
        order, _ = await create_order_from_cart(session, CUSTOMER, "Aziz", None, "+998", "Toshkent")
        assert order is not None
        assert await change_order_status(session, order.id, "shipping") is None  # skipping is refused
        reviewed = await change_order_status(session, order.id, "payment_review")
        assert reviewed is not None and reviewed.status == "payment_review"
        assert await change_order_status(session, order.id, "accepted") is None  # second click is a no-op
        assert await change_order_status(session, order.id, "cancelled") is not None
        assert await change_order_status(session, order.id, "ordered") is None


@pytest.mark.usefixtures("db")
async def test_owner_claim_works_once() -> None:
    async with async_session() as session:
        assert await claim_ownership(session, "wrong-code-xxxxxxxxxx", 111, "X") == "invalid"
        assert await claim_ownership(session, settings.OWNER_SETUP_CODE, 111, "Bek") == "claimed"
        assert await claim_ownership(session, settings.OWNER_SETUP_CODE, 111, "Bek") == "already_owner"
        assert await claim_ownership(session, settings.OWNER_SETUP_CODE, 333, "Thief") == "invalid"
        roles = (await session.execute(select(Admin.telegram_id, Admin.role))).all()
    assert [tuple(r) for r in roles] == [(111, "owner")]


@pytest.mark.usefixtures("db")
async def test_catalog_lists_only_in_stock_newest_first() -> None:
    old = await _product("Eski", 100_000)
    hidden = await _product("Tugagan", 100_000, in_stock=False)
    new = await _product("Yangi", 100_000)
    async with async_session() as session:
        ids = await catalog_product_ids(session, 0)
    assert hidden not in ids
    assert ids.index(new) < ids.index(old)
