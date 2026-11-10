import pytest
from datetime import datetime, timezone, timedelta
from sqlalchemy import select
from db.models import Order, CargoTracking, PromoCode


@pytest.mark.asyncio
async def test_cargo_tracking_creation_and_relationship(test_db_session):
    async with test_db_session() as session:
        # Create an order
        order = Order(
            user_id=12345,
            customer_name="Gulmira Customer",
            customer_username="gulmira_fan",
            items_snapshot=[{"product_id": 1, "title": "Aesthetic Jempir", "price": 99000, "qty": 1}],
            total=99000,
            estimated_cargo=12000,
            status="new",
            tracking_code="TRK-GULMIRA-1001",
        )
        session.add(order)
        await session.flush()

        # Create tracking
        tracking = CargoTracking(
            tracking_code="TRK-GULMIRA-1001",
            order_id=order.id,
            user_id=order.user_id,
            status="in_transit",
            current_location="Xitoy ombori (Urumqi)",
            status_description="Yuk jo'natishga tayyorlandi va yo'lga chiqdi",
            weight_grams=350,
            estimated_delivery=datetime.now(timezone.utc) + timedelta(days=12),
        )
        session.add(tracking)
        await session.commit()

    async with test_db_session() as session:
        res = await session.execute(
            select(CargoTracking).where(CargoTracking.tracking_code == "TRK-GULMIRA-1001")
        )
        saved_tracking = res.scalars().first()
        assert saved_tracking is not None
        assert saved_tracking.status == "in_transit"
        assert saved_tracking.current_location == "Xitoy ombori (Urumqi)"
        assert saved_tracking.order is not None
        assert saved_tracking.order.total == 99000
        assert saved_tracking.order.customer_name == "Gulmira Customer"


@pytest.mark.asyncio
async def test_promo_code_creation_and_validation(test_db_session):
    async with test_db_session() as session:
        # Create percentage promo code
        promo_percent = PromoCode(
            code="GULMIRA10",
            discount_percent=10,
            min_order_amount=50000,
            max_uses=100,
            is_active=True,
            valid_until=datetime.now(timezone.utc) + timedelta(days=30),
        )
        # Create fixed amount promo code
        promo_fixed = PromoCode(
            code="GULMIRA20K",
            discount_amount=20000,
            min_order_amount=100000,
            max_uses=50,
            is_active=True,
        )
        session.add_all([promo_percent, promo_fixed])
        await session.commit()

    async with test_db_session() as session:
        res = await session.execute(select(PromoCode).where(PromoCode.code == "GULMIRA10"))
        p1 = res.scalars().first()
        assert p1 is not None
        assert p1.discount_percent == 10
        assert p1.is_active is True
        assert p1.used_count == 0

        res2 = await session.execute(select(PromoCode).where(PromoCode.code == "GULMIRA20K"))
        p2 = res2.scalars().first()
        assert p2 is not None
        assert p2.discount_amount == 20000
