"""Payment flow tests use a temporary SQLite database and never contact Telegram."""

import base64
import hashlib
import hmac
import json
import time
from pathlib import Path
from urllib.parse import urlencode

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import func, select

from bekstyle.api.routes import cart, media, orders, products
from bekstyle.config import settings
from bekstyle.db import Admin, Category, DEFAULT_PRODUCTS, Order, Product, async_session, migrate_columns

PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a3ioAAAAASUVORK5CYII=")
CARD = "4916 9903 4816 9779"


def auth(user_id: int = 222) -> dict[str, str]:
    data = {"auth_date": str(int(time.time())), "user": json.dumps({"id": user_id, "first_name": "Sinov"})}
    secret = hmac.new(b"WebAppData", settings.BOT_TOKEN.encode(), hashlib.sha256).digest()
    check = "\n".join(f"{k}={v}" for k, v in sorted(data.items()))
    data["hash"] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return {"X-Telegram-Init-Data": urlencode(data)}


@pytest.fixture
async def client(db):
    app = FastAPI()
    app.include_router(orders.router, prefix="/api")
    app.include_router(media.router, prefix="/api")
    app.include_router(products.router, prefix="/api")
    app.include_router(cart.router, prefix="/api")
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as value:
        yield value


async def product(*, in_stock=True, demo=False) -> int:
    async with async_session() as session:
        category_id = await session.scalar(select(Category.id).limit(1))
        item = Product(
            title=DEFAULT_PRODUCTS[0]["title"] if demo else "Tasdiqlangan sinov futbolkasi",
            price=100_000, category_id=category_id,
            photos=DEFAULT_PRODUCTS[0]["photos"] if demo else ["real-product-file-id"],
            colors=["Qora"], sizes=["L"], in_stock=in_stock,
        )
        session.add(item)
        await session.commit()
        return item.id


def payload(pid: int, **changes) -> dict:
    item = {"product_id": pid, "title": "Soxta mijoz nomi", "price": 1, "color": "Qora", "size": "L", "qty": 2}
    item.update(changes)
    return {"customer_name": "Sinov mijoz", "phone": "+998901234567", "city": "Toshkent", "address": "Faqat sinov manzili", "items": [item]}


async def make_order(client, **kwargs):
    pid = await product(**kwargs)
    response = await client.post("/api/orders", headers=auth(), json=payload(pid))
    assert response.status_code == 200, response.text
    return response.json()


async def test_checkout_uses_server_price_title_and_idempotency(client):
    pid = await product()
    headers = {**auth(), "Idempotency-Key": "same-checkout-key"}
    first = await client.post("/api/orders", headers=headers, json=payload(pid))
    second = await client.post("/api/orders", headers=headers, json=payload(pid))
    assert first.status_code == second.status_code == 200
    assert first.json()["id"] == second.json()["id"]
    assert first.json()["total"] == 200_000
    assert first.json()["items"][0]["title"] == "Tasdiqlangan sinov futbolkasi"
    assert first.json()["status"] == "pending_payment"
    async with async_session() as session:
        assert await session.scalar(select(func.count(Order.id))) == 1
    # Order details must work in pending and paid states, not only payment_review.
    assert (await client.get(f"/api/orders/{first.json()['id']}", headers=auth())).status_code == 200


@pytest.mark.parametrize("changes", [{"size": "XXXL"}, {"size": None}, {"color": "Pushti"}, {"qty": 0}, {"qty": 100}])
async def test_checkout_rejects_invalid_variant_or_quantity(client, changes):
    pid = await product()
    response = await client.post("/api/orders", headers=auth(), json=payload(pid, **changes))
    assert response.status_code in {400, 409}
    async with async_session() as session:
        assert await session.scalar(select(func.count(Order.id))) == 0


async def test_checkout_rejects_missing_sold_out_and_demo_items(client):
    sold_out = await product(in_stock=False)
    demo = await product(demo=True)
    for pid in [999999, sold_out, demo]:
        response = await client.post("/api/orders", headers=auth(), json=payload(pid))
        assert response.status_code == 409, response.text
    sample = (await client.get(f"/api/products/{demo}")).json()
    assert sample["is_demo"] is True
    assert "namuna" in sample["description"].lower()


async def test_private_orders_require_verified_identity(client):
    item = await make_order(client)
    assert (await client.get("/api/orders/my")).status_code == 401
    assert (await client.get(f"/api/orders/{item['id']}", headers=auth(333))).status_code == 403
    assert (await client.get("/api/orders/my", headers=auth(333))).json() == []


async def test_receipt_persists_without_disk_and_is_private(client):
    order = await make_order(client)
    url = f"/api/orders/{order['id']}/receipt"
    response = await client.post(url, headers=auth(), data={"selected_card": CARD}, files={"file": ("receipt.png", PNG, "image/png")})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "payment_review"
    assert "receipt_bytes" not in body
    filename = body["receipt_url"].rsplit("/", 1)[-1]
    (Path(settings.DATA_DIR) / "receipts" / filename).unlink()
    downloaded = await client.get(body["receipt_url"], headers=auth())
    assert downloaded.status_code == 200
    assert downloaded.content == PNG
    assert "no-store" in downloaded.headers["cache-control"]
    assert (await client.get(body["receipt_url"])).status_code == 401
    assert (await client.get(body["receipt_url"], headers=auth(333))).status_code == 404
    repeat = await client.post(url, headers=auth(), data={"selected_card": CARD}, files={"file": ("receipt.png", PNG, "image/png")})
    assert repeat.status_code == 409


async def test_receipt_rejects_bad_card_and_disguised_file(client):
    order = await make_order(client)
    url = f"/api/orders/{order['id']}/receipt"
    bad_card = await client.post(url, headers=auth(), data={"selected_card": "wrong"}, files={"file": ("receipt.png", PNG, "image/png")})
    assert bad_card.status_code == 400
    bad_file = await client.post(url, headers=auth(), data={"selected_card": CARD}, files={"file": ("receipt.png", b"<html>not an image</html>", "text/html")})
    assert bad_file.status_code == 400
    async with async_session() as session:
        stored = await session.get(Order, order["id"])
        assert stored.status == "pending_payment" and stored.receipt_bytes is None


async def test_admin_payment_transition_requires_review(client):
    async with async_session() as session:
        session.add(Admin(telegram_id=111, role="owner"))
        await session.commit()
    order = await make_order(client)
    confirm = f"/api/orders/{order['id']}/confirm-payment"
    assert (await client.post(confirm, headers=auth())).status_code == 403
    assert (await client.post(confirm, headers=auth(111))).status_code == 409
    upload = await client.post(f"/api/orders/{order['id']}/receipt", headers=auth(), data={"selected_card": CARD}, files={"file": ("receipt.png", PNG, "image/png")})
    assert upload.status_code == 200
    assert (await client.post(confirm, headers=auth(111))).json()["status"] == "paid"
    assert (await client.post(confirm, headers=auth(111))).status_code == 409
    assert (await client.get(f"/api/orders/{order['id']}", headers=auth())).status_code == 200
    reject = await client.post(f"/api/orders/{order['id']}/reject-payment", headers=auth(111), data={"reason": "Sinov"})
    assert reject.status_code == 409


@pytest.mark.usefixtures("db")
async def test_additive_migrations_are_repeatable():
    await migrate_columns()
    await migrate_columns()


async def source_product():
    pid = await product()
    async with async_session() as session:
        item = await session.get(Product, pid)
        item.colors = ["Qora", "Oq"]
        item.sizes = ["L", "M"]
        item.source_key = "pdd:verified-test"
        item.source_details = {
            "source_url": "https://mobile.yangkeduo.com/goods.html?goods_id=123",
            "cost_inputs": {"yuan_rate": "1850"},
            "target_profit_som": 30000,
            "variants": [
                {"sku_id": "1", "color": "Qora", "size": "L", "cost_cny": "40", "in_stock": True},
                {"sku_id": "2", "color": "Oq", "size": "M", "cost_cny": "42", "in_stock": True},
                {"sku_id": "3", "color": "Qora", "size": "M", "cost_cny": "43", "in_stock": False},
            ],
        }
        await session.commit()
    return pid


async def test_source_catalog_exposes_only_available_pairs_without_private_costs(client):
    pid = await source_product()
    response = await client.get(f"/api/products/{pid}")
    body = response.json()
    assert body["available_variants"] == [{"color": "Qora", "size": "L"}, {"color": "Oq", "size": "M"}]
    for private_field in ("cost_cny", "cost_inputs", "source_details", "source_key", "source_url", "target_profit_som", "sku_id"):
        assert private_field not in response.text


async def test_source_cart_and_direct_order_reject_unavailable_pairs(client):
    pid = await source_product()
    for color, size in [("Qora", "M"), ("Oq", "L")]:
        response = await client.post("/api/cart", headers=auth(), json={"product_id": pid, "color": color, "size": size, "qty": 1})
        assert response.status_code == 409
        response = await client.post("/api/orders", headers=auth(), json=payload(pid, color=color, size=size))
        assert response.status_code == 409
    response = await client.post("/api/cart", headers=auth(), json={"product_id": pid, "color": "Qora", "size": "L", "qty": 1})
    assert response.status_code == 200
    async with async_session() as session:
        item = await session.get(Product, pid)
        details = dict(item.source_details)
        details["variants"] = [{**v, "in_stock": False} for v in details["variants"]]
        item.source_details = details
        await session.commit()
    response = await client.post("/api/orders", headers=auth(), json=payload(pid))
    assert response.status_code == 409


async def test_source_accessory_without_variant_axes_is_orderable(client):
    pid = await product()
    async with async_session() as session:
        item = await session.get(Product, pid)
        item.colors = []
        item.sizes = []
        item.source_key = "pdd:accessory-test"
        item.source_details = {"variants": [{"sku_id": "single", "color": None, "size": None, "in_stock": True}]}
        await session.commit()
    response = await client.get(f"/api/products/{pid}")
    assert response.json()["available_variants"] == [{"color": None, "size": None}]
    response = await client.post("/api/orders", headers=auth(), json=payload(pid, color=None, size=None))
    assert response.status_code == 200
