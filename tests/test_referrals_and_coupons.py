import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy import select, func

from bot.services.referral_service import (
    get_user_referral_link,
    process_referral_start,
    confirm_referral,
    revoke_referral_on_channel_leave,
    get_user_referral_stats,
    validate_and_calculate_coupon_discount,
)
from db.models import User, Referral, ReferralCoupon, Order, CartItem, Product, Setting, utcnow
from tests.conftest import generate_test_init_data


@pytest.mark.asyncio
async def test_referral_link_generation():
    link = get_user_referral_link("moonlight_chinese_bot", 123456)
    assert link == "https://t.me/moonlight_chinese_bot?start=ref_123456"

    link_with_at = get_user_referral_link("@moonlight_chinese_bot", 789)
    assert link_with_at == "https://t.me/moonlight_chinese_bot?start=ref_789"


@pytest.mark.asyncio
async def test_process_referral_start_self_and_bot_rejected(test_db_session):
    async with test_db_session() as session:
        # Self referral
        res = await process_referral_start(
            session=session,
            bot=None,
            invitee_id=111,
            invitee_full_name="Alice",
            invitee_username="alice",
            is_bot=False,
            referrer_id=111,
            is_new_user=True,
        )
        assert res["valid"] is False
        assert res["reason"] == "self_or_bot"

        # Bot referral
        res2 = await process_referral_start(
            session=session,
            bot=None,
            invitee_id=222,
            invitee_full_name="Botty",
            invitee_username="botty_bot",
            is_bot=True,
            referrer_id=111,
            is_new_user=True,
        )
        assert res2["valid"] is False
        assert res2["reason"] == "self_or_bot"


@pytest.mark.asyncio
async def test_process_referral_start_existing_user_rejected(test_db_session):
    async with test_db_session() as session:
        # Create referrer
        referrer = User(telegram_id=1000, name="Referrer", first_seen=utcnow(), last_seen=utcnow())
        session.add(referrer)
        await session.commit()

        # Existing user tries to click referral link
        res = await process_referral_start(
            session=session,
            bot=None,
            invitee_id=2000,
            invitee_full_name="Old User",
            invitee_username="olduser",
            is_bot=False,
            referrer_id=1000,
            is_new_user=False,
        )
        assert res["valid"] is False
        assert res["reason"] == "existing_user"


@pytest.mark.asyncio
async def test_process_referral_start_new_user_success(test_db_session):
    async with test_db_session() as session:
        referrer = User(telegram_id=3000, name="Referrer", first_seen=utcnow(), last_seen=utcnow())
        session.add(referrer)
        await session.commit()

        mock_bot = MagicMock()
        mock_chat_member = MagicMock()
        mock_chat_member.status = "left"
        mock_bot.get_chat_member = AsyncMock(return_value=mock_chat_member)

        res = await process_referral_start(
            session=session,
            bot=mock_bot,
            invitee_id=4000,
            invitee_full_name="New Friend",
            invitee_username="newfriend",
            is_bot=False,
            referrer_id=3000,
            is_new_user=True,
        )
        assert res["valid"] is True
        assert res["was_member_before"] is False
        assert res["already_registered"] is False

        # Verify DB entry
        ref_db = await session.execute(select(Referral).where(Referral.invitee_id == 4000))
        ref = ref_db.scalars().first()
        assert ref is not None
        assert ref.referrer_id == 3000
        assert ref.status == "pending"


@pytest.mark.asyncio
async def test_confirm_referral_membership_and_milestones(test_db_session):
    async with test_db_session() as session:
        # Set channel ID in settings
        ch_setting = await session.execute(select(Setting).where(Setting.key == "channel_id"))
        s_obj = ch_setting.scalars().first()
        if s_obj:
            s_obj.value = "-1001234567890"
        else:
            session.add(Setting(key="channel_id", value="-1001234567890"))

        referrer = User(telegram_id=5000, name="Active Referrer", first_seen=utcnow(), last_seen=utcnow())
        session.add(referrer)
        await session.commit()

        mock_bot = MagicMock()
        mock_bot.send_message = AsyncMock()

        # Simulate 5 friend referrals joining one by one
        for i in range(1, 6):
            invitee_id = 6000 + i
            invitee_user = User(telegram_id=invitee_id, name=f"Friend {i}", first_seen=utcnow(), last_seen=utcnow())
            session.add(invitee_user)
            await session.commit()

            # Process start
            mock_member_left = MagicMock()
            mock_member_left.status = "left"
            mock_bot.get_chat_member = AsyncMock(return_value=mock_member_left)

            await process_referral_start(
                session=session,
                bot=mock_bot,
                invitee_id=invitee_id,
                invitee_full_name=f"Friend {i}",
                invitee_username=f"friend_{i}",
                is_bot=False,
                referrer_id=5000,
                is_new_user=True,
            )

            # Confirm subscription (member now subscribed)
            mock_member_joined = MagicMock()
            mock_member_joined.status = "member"
            mock_bot.get_chat_member = AsyncMock(return_value=mock_member_joined)

            conf_res = await confirm_referral(
                session=session,
                bot=mock_bot,
                invitee_id=invitee_id,
                referrer_id=5000,
                bot_username="moonlight_chinese_bot",
            )
            assert conf_res["status"] == "success"

        # Check total confirmed referrals
        cnt_res = await session.execute(
            select(func.count(Referral.id)).where(Referral.referrer_id == 5000, Referral.status == "confirmed")
        )
        assert cnt_res.scalar() == 5

        # Check that exactly ONE 20% discount coupon was minted for milestone 5!
        coupons_res = await session.execute(
            select(ReferralCoupon).where(ReferralCoupon.user_id == 5000)
        )
        coupons = coupons_res.scalars().all()
        assert len(coupons) == 1
        c5 = coupons[0]
        assert c5.milestone == 5
        assert c5.discount_percent == 20
        assert c5.is_used is False
        assert c5.code.startswith("REF20-")

        # Now simulate 5 more friends (total 10)
        for i in range(6, 11):
            invitee_id = 6000 + i
            invitee_user = User(telegram_id=invitee_id, name=f"Friend {i}", first_seen=utcnow(), last_seen=utcnow())
            session.add(invitee_user)
            await session.commit()

            mock_member_left = MagicMock()
            mock_member_left.status = "left"
            mock_bot.get_chat_member = AsyncMock(return_value=mock_member_left)

            await process_referral_start(
                session=session,
                bot=mock_bot,
                invitee_id=invitee_id,
                invitee_full_name=f"Friend {i}",
                invitee_username=f"friend_{i}",
                is_bot=False,
                referrer_id=5000,
                is_new_user=True,
            )

            mock_member_joined = MagicMock()
            mock_member_joined.status = "member"
            mock_bot.get_chat_member = AsyncMock(return_value=mock_member_joined)

            await confirm_referral(
                session=session,
                bot=mock_bot,
                invitee_id=invitee_id,
                referrer_id=5000,
                bot_username="moonlight_chinese_bot",
            )

        # Check coupons count now: should be exactly 2 (milestones 5 and 10)!
        coupons_res2 = await session.execute(
            select(ReferralCoupon).where(ReferralCoupon.user_id == 5000).order_by(ReferralCoupon.milestone.asc())
        )
        coupons2 = coupons_res2.scalars().all()
        assert len(coupons2) == 2
        assert coupons2[0].milestone == 5
        assert coupons2[1].milestone == 10
        assert coupons2[0].code != coupons2[1].code


@pytest.mark.asyncio
async def test_referral_revocation_on_channel_leave(test_db_session):
    async with test_db_session() as session:
        # Referrer and invitee
        referrer = User(telegram_id=7000, name="Ref", first_seen=utcnow(), last_seen=utcnow())
        invitee = User(telegram_id=7001, name="Inv", first_seen=utcnow(), last_seen=utcnow())
        session.add_all([referrer, invitee])

        # Confirmed referral
        ref = Referral(
            referrer_id=7000,
            invitee_id=7001,
            status="confirmed",
            was_member_before=False,
            created_at=utcnow(),
            confirmed_at=utcnow(),
        )
        session.add(ref)
        await session.commit()

        mock_bot = MagicMock()
        mock_bot.send_message = AsyncMock()

        new_count = await revoke_referral_on_channel_leave(session, mock_bot, 7001)
        assert new_count == 0

        # Verify DB status is revoked
        ref_updated = (await session.execute(select(Referral).where(Referral.invitee_id == 7001))).scalars().first()
        assert ref_updated.status == "revoked"
        assert ref_updated.revoked_at is not None


@pytest.mark.asyncio
async def test_coupon_discount_calculation_and_lock(test_db_session):
    async with test_db_session() as session:
        user_id = 8000
        user = User(telegram_id=user_id, name="Shopper", first_seen=utcnow(), last_seen=utcnow())
        session.add(user)

        # Give user 5 confirmed referrals
        for i in range(5):
            u_f = User(telegram_id=8100 + i, name=f"F{i}", first_seen=utcnow(), last_seen=utcnow())
            session.add(u_f)
            session.add(Referral(referrer_id=user_id, invitee_id=8100 + i, status="confirmed", created_at=utcnow()))

        # Add milestone 5 coupon
        coupon = ReferralCoupon(
            user_id=user_id,
            code="REF20-TEST-COUP",
            discount_percent=20,
            milestone=5,
            is_used=False,
            created_at=utcnow(),
        )
        session.add(coupon)
        await session.commit()

        cart_items = [
            {"product_id": 1, "title": "Aesthetic Jempir 🌸", "price": 100000, "qty": 1},
            {"product_id": 2, "title": "Pink Wig 💇‍♀️", "price": 200000, "qty": 2},
        ]

        # 1. Default (no selected_product_id): chooses highest priced item (Pink Wig, 200,000)
        calc1 = await validate_and_calculate_coupon_discount(session, user_id, "REF20-TEST-COUP", cart_items)
        assert calc1["valid"] is True
        assert calc1["product_id"] == 2
        # 20% of 200,000 is 40,000
        assert calc1["discount_amount"] == 40000

        # 2. Chosen product_id = 1 (Aesthetic Jempir, 100,000)
        calc2 = await validate_and_calculate_coupon_discount(session, user_id, "REF20-TEST-COUP", cart_items, selected_product_id=1)
        assert calc2["valid"] is True
        assert calc2["product_id"] == 1
        # 20% of 100,000 is 20,000
        assert calc2["discount_amount"] == 20000

        # 3. If referrals drop below 5 (e.g. 1 friend leaves):
        one_ref = (await session.execute(select(Referral).where(Referral.referrer_id == user_id))).scalars().first()
        one_ref.status = "revoked"
        await session.commit()

        # Attempt to use coupon when active friends = 4 (< 5):
        calc_locked = await validate_and_calculate_coupon_discount(session, user_id, "REF20-TEST-COUP", cart_items)
        assert calc_locked["valid"] is False
        assert "kamida 5 ta faol" in calc_locked["message"]


@pytest.mark.asyncio
async def test_api_referrals_and_checkout(client, test_db_session):
    user_id = 9000
    init_data = generate_test_init_data(user_id=user_id, first_name="GulmiraCustomer")
    headers = {"X-Telegram-Init-Data": init_data}

    async with test_db_session() as session:
        # Create user
        u = User(telegram_id=user_id, name="GulmiraCustomer", first_seen=utcnow(), last_seen=utcnow())
        session.add(u)

        # Create 5 confirmed referrals
        for i in range(5):
            fid = 9100 + i
            session.add(User(telegram_id=fid, name=f"Friend {i}", first_seen=utcnow(), last_seen=utcnow()))
            session.add(Referral(referrer_id=user_id, invitee_id=fid, status="confirmed", created_at=utcnow()))

        # Create coupon
        coupon = ReferralCoupon(
            user_id=user_id,
            code="REF20-API-TEST",
            discount_percent=20,
            milestone=5,
            is_used=False,
            created_at=utcnow(),
        )
        session.add(coupon)

        # Add item to cart
        session.add(CartItem(user_id=user_id, product_id=1, qty=1))
        await session.commit()

    # 1. Test GET /api/referrals/me
    resp = await client.get("/api/referrals/me", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["confirmed_count"] == 5
    assert len(data["available_coupons"]) == 1
    assert data["available_coupons"][0]["code"] == "REF20-API-TEST"
    assert data["friends_needed_for_next"] == 5

    # 2. Test POST /api/referrals/validate-coupon
    val_resp = await client.post(
        "/api/referrals/validate-coupon",
        headers=headers,
        json={"code": "REF20-API-TEST", "product_id": 1},
    )
    assert val_resp.status_code == 200
    val_data = val_resp.json()
    assert val_data["valid"] is True
    # Product 1 price is 99,000 -> 20% discount = 19,800
    assert val_data["discount_amount"] == 19800

    # 3. Test POST /api/orders with coupon
    with patch("api.routes.orders.send_payment_instructions"):
        order_resp = await client.post(
            "/api/orders",
            headers=headers,
            json={
                "customer_name": "GulmiraCustomer",
                "coupon_code": "REF20-API-TEST",
                "coupon_product_id": 1,
                "use_cashback": 0,
            },
        )
        assert order_resp.status_code == 200
        order_data = order_resp.json()
        assert order_data["promo_code"] == "REF20-API-TEST"
        assert order_data["discount_amount"] == 19800
        assert order_data["total"] == 99000 - 19800  # 79200

        # 4. Verify coupon is now marked is_used in DB
        async with test_db_session() as session:
            c_db = (await session.execute(select(ReferralCoupon).where(ReferralCoupon.code == "REF20-API-TEST"))).scalars().first()
            assert c_db.is_used is True
            assert c_db.order_id == order_data["id"]
            assert c_db.discount_amount == 19800

        # 5. Attempting to use the coupon again should be rejected
        async with test_db_session() as session:
            session.add(CartItem(user_id=user_id, product_id=1, qty=1))
            await session.commit()

        order_resp_reuse = await client.post(
            "/api/orders",
            headers=headers,
            json={
                "customer_name": "GulmiraCustomer",
                "coupon_code": "REF20-API-TEST",
                "coupon_product_id": 1,
            },
        )
        assert order_resp_reuse.status_code == 400
        assert "allaqachon ishlatilgan" in order_resp_reuse.json()["detail"]


@pytest.mark.asyncio
async def test_scaling_milestones_5_10_15_20(test_db_session):
    """
    Explicitly tests scaling milestones:
    5 invites = 1st coupon,
    10 invites = 2nd coupon,
    15 invites = 3rd coupon,
    20 invites = 4th coupon.
    """
    async with test_db_session() as session:
        # Set channel ID
        ch_s = (await session.execute(select(Setting).where(Setting.key == "channel_id"))).scalars().first()
        if ch_s:
            ch_s.value = "-1001234567890"
        else:
            session.add(Setting(key="channel_id", value="-1001234567890"))

        referrer_id = 95000
        session.add(User(telegram_id=referrer_id, name="Big Influencer", first_seen=utcnow(), last_seen=utcnow()))
        await session.commit()

        mock_bot = MagicMock()
        mock_bot.send_message = AsyncMock()

        # Simulate 20 verified friend invites
        for i in range(1, 21):
            invitee_id = 96000 + i
            session.add(User(telegram_id=invitee_id, name=f"Invitee {i}", first_seen=utcnow(), last_seen=utcnow()))
            session.add(Referral(referrer_id=referrer_id, invitee_id=invitee_id, status="pending", created_at=utcnow()))
            await session.commit()

            # Member confirmed
            mock_member = MagicMock()
            mock_member.status = "member"
            mock_bot.get_chat_member = AsyncMock(return_value=mock_member)

            await confirm_referral(
                session=session,
                bot=mock_bot,
                invitee_id=invitee_id,
                referrer_id=referrer_id,
                bot_username="moonlight_chinese_bot",
            )

            # Check coupons at milestone boundaries
            coupons_so_far = (await session.execute(
                select(ReferralCoupon).where(ReferralCoupon.user_id == referrer_id)
            )).scalars().all()

            expected_coupons_count = i // 5
            assert len(coupons_so_far) == expected_coupons_count

        # At 20 invites: exactly 4 distinct coupons!
        final_coupons = (await session.execute(
            select(ReferralCoupon).where(ReferralCoupon.user_id == referrer_id).order_by(ReferralCoupon.milestone.asc())
        )).scalars().all()
        assert len(final_coupons) == 4
        milestones = [c.milestone for c in final_coupons]
        assert milestones == [5, 10, 15, 20]
        # Every coupon has 20% discount
        assert all(c.discount_percent == 20 for c in final_coupons)
        # Every coupon code is unique
        codes = [c.code for c in final_coupons]
        assert len(set(codes)) == 4


@pytest.mark.asyncio
async def test_relock_and_unlock_coupon_on_fluctuating_referrals(test_db_session):
    """
    Tests that if a friend leaves and verified referrals drop to 4,
    the 20% coupon is locked. When another friend joins and count reaches 5 again,
    the coupon unlocks and becomes usable!
    """
    async with test_db_session() as session:
        # Set channel ID
        ch_s = (await session.execute(select(Setting).where(Setting.key == "channel_id"))).scalars().first()
        if ch_s:
            ch_s.value = "-1001234567890"
        else:
            session.add(Setting(key="channel_id", value="-1001234567890"))

        user_id = 98000
        session.add(User(telegram_id=user_id, name="TestFluctuate", first_seen=utcnow(), last_seen=utcnow()))

        # 5 friends
        for i in range(1, 6):
            fid = 98100 + i
            session.add(User(telegram_id=fid, name=f"F{i}", first_seen=utcnow(), last_seen=utcnow()))
            session.add(Referral(referrer_id=user_id, invitee_id=fid, status="confirmed", created_at=utcnow()))

        coupon = ReferralCoupon(
            user_id=user_id,
            code="REF20-FLUCTUATE",
            discount_percent=20,
            milestone=5,
            is_used=False,
            created_at=utcnow(),
        )
        session.add(coupon)
        await session.commit()

        cart = [{"product_id": 1, "title": "Jempir", "price": 100000, "qty": 1}]

        # 1. 5 friends -> valid
        v1 = await validate_and_calculate_coupon_discount(session, user_id, "REF20-FLUCTUATE", cart)
        assert v1["valid"] is True
        assert v1["discount_amount"] == 20000

        # 2. Friend leaves -> count = 4 -> coupon locked
        mock_bot = MagicMock()
        mock_bot.send_message = AsyncMock()
        await revoke_referral_on_channel_leave(session, mock_bot, 98101)

        v2 = await validate_and_calculate_coupon_discount(session, user_id, "REF20-FLUCTUATE", cart)
        assert v2["valid"] is False
        assert "kamida 5 ta faol" in v2["message"]

        # 3. New friend joins -> count = 5 again -> coupon unlocked!
        new_fid = 98199
        session.add(User(telegram_id=new_fid, name="New replacement", first_seen=utcnow(), last_seen=utcnow()))
        session.add(Referral(referrer_id=user_id, invitee_id=new_fid, status="pending", created_at=utcnow()))
        await session.commit()

        mock_member = MagicMock()
        mock_member.status = "member"
        mock_bot.get_chat_member = AsyncMock(return_value=mock_member)

        await confirm_referral(
            session=session,
            bot=mock_bot,
            invitee_id=new_fid,
            referrer_id=user_id,
            bot_username="moonlight_chinese_bot",
        )

        v3 = await validate_and_calculate_coupon_discount(session, user_id, "REF20-FLUCTUATE", cart)
        assert v3["valid"] is True
        assert v3["discount_amount"] == 20000


@pytest.mark.asyncio
async def test_bot_referral_dashboard_and_confirm_callback(test_db_session):
    """
    Tests bot UI handlers:
    - handle_referral_menu message handler
    - handle_confirm_referral_callback callback handler
    """
    from bot.handlers.referral import handle_referral_menu, handle_confirm_referral_callback
    from aiogram.types import Message, CallbackQuery, User as AiogramUser, Chat

    async with test_db_session() as session:
        # Set channel ID
        ch_s = (await session.execute(select(Setting).where(Setting.key == "channel_id"))).scalars().first()
        if ch_s:
            ch_s.value = "-1001234567890"
        else:
            session.add(Setting(key="channel_id", value="-1001234567890"))

        u1 = User(telegram_id=77001, name="Alice", first_seen=utcnow(), last_seen=utcnow())
        u2 = User(telegram_id=77002, name="Bob", first_seen=utcnow(), last_seen=utcnow())
        session.add_all([u1, u2])

        # Bob invited by Alice (pending)
        ref = Referral(referrer_id=77001, invitee_id=77002, status="pending", created_at=utcnow())
        session.add(ref)
        await session.commit()

    # Mock Telegram Bot
    mock_bot = MagicMock()
    mock_bot_user = MagicMock()
    mock_bot_user.username = "moonlight_chinese_bot"
    mock_bot.get_me = AsyncMock(return_value=mock_bot_user)
    mock_member = MagicMock()
    mock_member.status = "member"
    mock_bot.get_chat_member = AsyncMock(return_value=mock_member)
    mock_bot.send_message = AsyncMock()

    from types import SimpleNamespace

    # 1. Test Alice opening referral menu
    msg = SimpleNamespace(
        message_id=1,
        chat=SimpleNamespace(id=77001, type="private"),
        from_user=SimpleNamespace(id=77001, is_bot=False, first_name="Alice"),
        text="👥 Do'stlarni taklif qilish (20% chegirma)",
        bot=mock_bot,
        answer=AsyncMock(),
    )

    with patch("bot.handlers.referral.is_user_admin", AsyncMock(return_value=True)), \
         patch("bot.handlers.referral.async_session_factory", test_db_session):
        await handle_referral_menu(msg)
        assert msg.answer.called
        call_text = msg.answer.call_args[0][0]
        assert "DO'STLARNI TAKLIF QILISH" in call_text
        assert "ref_77001" in call_text

    # 2. Test Bob clicking ✅ Tasdiqlash
    cb_msg = SimpleNamespace(edit_text=AsyncMock(), answer=AsyncMock())
    cb = SimpleNamespace(
        id="cb1",
        from_user=SimpleNamespace(id=77002, is_bot=False, first_name="Bob"),
        chat_instance="chat1",
        data="confirm_ref:77001:77002",
        message=cb_msg,
        bot=mock_bot,
        answer=AsyncMock(),
    )

    with patch("bot.handlers.referral.async_session_factory", test_db_session):
        await handle_confirm_referral_callback(cb)
        assert cb.answer.called
        assert cb_msg.edit_text.called
        edit_text = cb_msg.edit_text.call_args[0][0]
        assert "muvaffaqiyatli tasdiqlandi" in edit_text or "Tasdiqlandi" in edit_text

    # Verify referral status is now confirmed in DB
    async with test_db_session() as session:
        ref_db = (await session.execute(select(Referral).where(Referral.invitee_id == 77002))).scalars().first()
        assert ref_db.status == "confirmed"


@pytest.mark.asyncio
async def test_legitimate_invitee_reopens_referral_link_not_rejected(test_db_session):
    """
    Critical Bug Fix Verification:
    A legitimate invitee opens the referral link, which registers their pending referral.
    If they re-click or reopen the link, they MUST NOT be rejected with 'existing_user'!
    They should receive valid=True with already_registered=True and confirmation access.
    """
    async with test_db_session() as session:
        ref_user = User(telegram_id=88001, name="Referrer", first_seen=utcnow(), last_seen=utcnow())
        session.add(ref_user)
        await session.commit()

        # 1. First click: invitee is new user
        res1 = await process_referral_start(
            session=session,
            bot=None,
            invitee_id=88002,
            invitee_full_name="New Invitee",
            invitee_username="new_invitee",
            is_bot=False,
            referrer_id=88001,
            is_new_user=True,
        )
        assert res1["valid"] is True
        assert res1["already_registered"] is False

        # Add invitee to User table (as happens during normal /start)
        session.add(User(telegram_id=88002, name="New Invitee", first_seen=utcnow(), last_seen=utcnow()))
        await session.commit()

        # 2. Second click: invitee now already in DB (is_new_user=False), re-clicking same referrer link
        res2 = await process_referral_start(
            session=session,
            bot=None,
            invitee_id=88002,
            invitee_full_name="New Invitee",
            invitee_username="new_invitee",
            is_bot=False,
            referrer_id=88001,
            is_new_user=False,  # Already in users table
        )
        assert res2["valid"] is True
        assert res2["already_registered"] is True
        assert res2["referral"].referrer_id == 88001

        # 3. Third party tries to refer the same invitee -> rejected
        session.add(User(telegram_id=99999, name="Third Party", first_seen=utcnow(), last_seen=utcnow()))
        await session.commit()

        res3 = await process_referral_start(
            session=session,
            bot=None,
            invitee_id=88002,
            invitee_full_name="New Invitee",
            invitee_username="new_invitee",
            is_bot=False,
            referrer_id=99999,
            is_new_user=False,
        )
        assert res3["valid"] is False
        assert res3["reason"] == "already_referred_by_other"


@pytest.mark.asyncio
async def test_was_member_before_sets_status_and_honest_accounting(test_db_session):
    """
    Tests that if an invited user was already in the channel:
    - Referral status is set to 'was_member_before' (not pending)
    - confirm_referral does not grant point
    - Referrer's pending count is 0
    """
    async with test_db_session() as session:
        # Set channel ID
        ch_s = (await session.execute(select(Setting).where(Setting.key == "channel_id"))).scalars().first()
        if ch_s:
            ch_s.value = "-1001234567890"
        else:
            session.add(Setting(key="channel_id", value="-1001234567890"))

        referrer = User(telegram_id=89001, name="Referrer", first_seen=utcnow(), last_seen=utcnow())
        session.add(referrer)
        await session.commit()

        mock_bot = MagicMock()
        mock_member = MagicMock()
        mock_member.status = "member"
        mock_bot.get_chat_member = AsyncMock(return_value=mock_member)

        # Invitee already in channel
        res = await process_referral_start(
            session=session,
            bot=mock_bot,
            invitee_id=89002,
            invitee_full_name="Existing Channel Member",
            invitee_username="member_fan",
            is_bot=False,
            referrer_id=89001,
            is_new_user=True,
        )
        assert res["valid"] is True
        assert res["was_member_before"] is True

        # Check DB status is was_member_before (not pending)
        ref_db = (await session.execute(select(Referral).where(Referral.invitee_id == 89002))).scalars().first()
        assert ref_db.status == "was_member_before"

        # Check pending count for referrer
        stats = await get_user_referral_stats(session, 89001, "moonlight_chinese_bot")
        assert stats["pending_count"] == 0
        assert stats["confirmed_count"] == 0


@pytest.mark.asyncio
async def test_auto_confirm_channel_join_event(test_db_session):
    """
    Tests that when an invitee with a pending referral joins the channel directly,
    handle_channel_member_updated automatically confirms the referral without
    requiring manual button tap!
    """
    from bot.handlers.channel_member import handle_channel_member_updated
    from types import SimpleNamespace

    async with test_db_session() as session:
        # Set channel ID
        ch_s = (await session.execute(select(Setting).where(Setting.key == "channel_id"))).scalars().first()
        if ch_s:
            ch_s.value = "-1001234567890"
        else:
            session.add(Setting(key="channel_id", value="-1001234567890"))

        referrer = User(telegram_id=91001, name="Referrer", first_seen=utcnow(), last_seen=utcnow())
        invitee = User(telegram_id=91002, name="New Joiner", first_seen=utcnow(), last_seen=utcnow())
        session.add_all([referrer, invitee])

        # Pending referral
        session.add(Referral(referrer_id=91001, invitee_id=91002, status="pending", created_at=utcnow()))
        await session.commit()

    mock_bot = MagicMock()
    mock_bot_user = MagicMock(id=999999, username="moonlight_chinese_bot")
    mock_bot.get_me = AsyncMock(return_value=mock_bot_user)
    mock_bot.get_chat_member = AsyncMock(return_value=SimpleNamespace(status="member"))
    mock_bot.send_message = AsyncMock()

    # ChatMemberUpdated event: user was left, now joined (member)
    event = SimpleNamespace(
        bot=mock_bot,
        chat=SimpleNamespace(id=-1001234567890),
        old_chat_member=SimpleNamespace(status="left"),
        new_chat_member=SimpleNamespace(status="member", user=SimpleNamespace(id=91002)),
    )

    with patch("bot.handlers.channel_member.async_session_factory", test_db_session):
        await handle_channel_member_updated(event)

    # Verify referral was auto-confirmed in DB!
    async with test_db_session() as session:
        ref_db = (await session.execute(select(Referral).where(Referral.invitee_id == 91002))).scalars().first()
        assert ref_db.status == "confirmed"


@pytest.mark.asyncio
async def test_admin_order_cancellation_reactivates_referral_coupon(client, test_db_session):
    """
    Tests that when an order using a 20% coupon is cancelled by admin:
    - The coupon is reactivated (is_used=False, order_id=None)
    - The customer can reuse the coupon!
    """
    admin_id = 92000
    user_id = 92001
    admin_init = generate_test_init_data(user_id=admin_id, first_name="AdminOwner")
    user_init = generate_test_init_data(user_id=user_id, first_name="GulmiraShopper")

    admin_headers = {"X-Telegram-Init-Data": admin_init}
    user_headers = {"X-Telegram-Init-Data": user_init}

    from db.models import Admin, PromoCode

    async with test_db_session() as session:
        session.add(Admin(telegram_id=admin_id, name="AdminOwner", role="owner"))
        session.add(User(telegram_id=admin_id, name="AdminOwner"))
        session.add(User(telegram_id=user_id, name="GulmiraShopper"))

        # Add 5 confirmed referrals for user
        for i in range(5):
            fid = 92100 + i
            session.add(User(telegram_id=fid, name=f"F{i}"))
            session.add(Referral(referrer_id=user_id, invitee_id=fid, status="confirmed", created_at=utcnow()))

        # Add coupon
        coupon = ReferralCoupon(
            user_id=user_id,
            code="REF20-REFUND-TEST",
            discount_percent=20,
            milestone=5,
            is_used=False,
            created_at=utcnow(),
        )
        session.add(coupon)
        session.add(PromoCode(code="REF20-REFUND-TEST", discount_percent=20, is_active=True))

        # Add cart item
        session.add(CartItem(user_id=user_id, product_id=1, qty=1))
        await session.commit()

    # 1. Place order using coupon
    with patch("api.routes.orders.send_payment_instructions"):
        order_resp = await client.post(
            "/api/orders",
            headers=user_headers,
            json={
                "customer_name": "GulmiraShopper",
                "coupon_code": "REF20-REFUND-TEST",
                "coupon_product_id": 1,
            },
        )
        assert order_resp.status_code == 200
        order_id = order_resp.json()["id"]

    # Verify coupon is used
    async with test_db_session() as session:
        c1 = (await session.execute(select(ReferralCoupon).where(ReferralCoupon.code == "REF20-REFUND-TEST"))).scalars().first()
        assert c1.is_used is True
        assert c1.order_id == order_id

    # 2. Admin cancels the order
    with patch("api.routes.admin.bot", MagicMock()):
        cancel_resp = await client.patch(
            f"/api/admin/orders/{order_id}/status",
            headers=admin_headers,
            json={"status": "cancelled"},
        )
        assert cancel_resp.status_code == 200

    # 3. Verify coupon is now REACTIVATED in DB!
    async with test_db_session() as session:
        c2 = (await session.execute(select(ReferralCoupon).where(ReferralCoupon.code == "REF20-REFUND-TEST"))).scalars().first()
        assert c2.is_used is False
        assert c2.order_id is None
        assert c2.discount_amount == 0


@pytest.mark.asyncio
async def test_standard_promocode_fallback(test_db_session):
    """
    Tests that standard PromoCode (percentage and fixed amount) works seamlessly
    in validate_and_calculate_coupon_discount as a fallback!
    """
    from db.models import PromoCode

    async with test_db_session() as session:
        # Create standard percentage promo
        p_pct = PromoCode(
            code="SPRING15",
            discount_percent=15,
            is_active=True,
            created_at=utcnow(),
        )
        # Create standard fixed promo
        p_fix = PromoCode(
            code="SAVE10K",
            discount_amount=10000,
            is_active=True,
            created_at=utcnow(),
        )
        session.add_all([p_pct, p_fix])
        await session.commit()

        cart = [{"product_id": 1, "title": "Aesthetic Jempir", "price": 100000, "qty": 1}]

        # Test percentage promo
        res1 = await validate_and_calculate_coupon_discount(session, 1234, "SPRING15", cart)
        assert res1["valid"] is True
        assert res1["discount_amount"] == 15000  # 15% of 100,000

        # Test fixed amount promo
        res2 = await validate_and_calculate_coupon_discount(session, 1234, "SAVE10K", cart)
        assert res2["valid"] is True
        assert res2["discount_amount"] == 10000


@pytest.mark.asyncio
async def test_concurrent_checkout_prevents_double_spend(client, test_db_session):
    """
    Tests atomic double-spend prevention on ReferralCoupon:
    1. First atomic update on active coupon matches rowcount == 1.
    2. Any concurrent / subsequent update with where(is_used==False) yields rowcount == 0,
       causing create_order to raise 400 Bad Request.
    """
    from sqlalchemy import update
    user_id = 93000
    user_init = generate_test_init_data(user_id=user_id, first_name="ConcurrentUser")
    headers = {"X-Telegram-Init-Data": user_init}

    async with test_db_session() as session:
        session.add(User(telegram_id=user_id, name="ConcurrentUser"))
        for i in range(5):
            fid = 93100 + i
            session.add(User(telegram_id=fid, name=f"F{i}"))
            session.add(Referral(referrer_id=user_id, invitee_id=fid, status="confirmed", created_at=utcnow()))

        coupon = ReferralCoupon(
            user_id=user_id,
            code="REF20-RACE-GUARD",
            discount_percent=20,
            milestone=5,
            is_used=False,
            created_at=utcnow(),
        )
        session.add(coupon)
        session.add(CartItem(user_id=user_id, product_id=1, qty=1))
        await session.commit()

        # Test atomic condition directly in database session
        stmt1 = (
            update(ReferralCoupon)
            .where(ReferralCoupon.code == "REF20-RACE-GUARD", ReferralCoupon.is_used == False)
            .values(is_used=True, used_at=utcnow())
        )
        res1 = await session.execute(stmt1)
        assert res1.rowcount == 1

        # Concurrent attempt to update the same coupon while where(is_used == False)
        stmt2 = (
            update(ReferralCoupon)
            .where(ReferralCoupon.code == "REF20-RACE-GUARD", ReferralCoupon.is_used == False)
            .values(is_used=True, used_at=utcnow())
        )
        res2 = await session.execute(stmt2)
        assert res2.rowcount == 0  # Atomic check rejected concurrent double-spend!

        # Reset for API check
        coupon.is_used = False
        await session.commit()

    with patch("api.routes.orders.send_payment_instructions"):
        # Order 1: Successfully consumes coupon
        resp1 = await client.post(
            "/api/orders",
            headers=headers,
            json={
                "customer_name": "ConcurrentUser",
                "coupon_code": "REF20-RACE-GUARD",
                "coupon_product_id": 1,
            },
        )
        assert resp1.status_code == 200

        # Order 2: Reusing consumed coupon is rejected
        async with test_db_session() as session:
            session.add(CartItem(user_id=user_id, product_id=1, qty=1))
            await session.commit()

        resp2 = await client.post(
            "/api/orders",
            headers=headers,
            json={
                "customer_name": "ConcurrentUser",
                "coupon_code": "REF20-RACE-GUARD",
                "coupon_product_id": 1,
            },
        )
        assert resp2.status_code == 400
        assert "allaqachon ishlatilgan" in resp2.json()["detail"]



