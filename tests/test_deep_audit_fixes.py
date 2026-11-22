"""Regression tests for all critical, security, and functional bugs found in the deep bot audit."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiogram import Dispatcher
from aiogram.enums import ChatMemberStatus
from aiogram.filters import CommandObject
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    CallbackQuery,
    Chat,
    ChatMemberAdministrator,
    ChatMemberLeft,
    ChatMemberMember,
    ChatMemberUpdated,
    Message,
    PhotoSize,
    Update,
    User as TgUser,
)
from sqlalchemy import select

from db.models import (
    Admin,
    CartItem,
    Contest,
    Order,
    Product,
    PromoCode,
    Referral,
    ReferralCoupon,
    Setting,
    User,
    utcnow,
)
from tests.conftest import generate_test_init_data


@pytest.mark.asyncio
async def test_e2e_chat_member_dispatcher_join_and_leave(test_db_session):
    """
    E2E aiogram Dispatcher.feed_update test for @router.chat_member():
    1. Joining the linked channel auto-confirms a pending Referral (without throttling immediate Tasdiqlash).
    2. Leaving the linked channel revokes the Referral and locks the unused PromoCode.
    """
    from bot.handlers.channel_member import router as channel_member_router
    from bot.services.referral_service import confirm_referral

    channel_id = -1004378811161
    referrer_id = 70001
    invitee_id = 70002

    async with test_db_session() as session:
        ch = (await session.execute(select(Setting).where(Setting.key == "channel_id"))).scalars().first()
        ch.value = str(channel_id)
        session.add_all([
            User(telegram_id=referrer_id, name="Referrer", first_seen=utcnow(), last_seen=utcnow()),
            User(telegram_id=invitee_id, name="Invitee", first_seen=utcnow(), last_seen=utcnow()),
            Referral(
                referrer_id=referrer_id,
                invitee_id=invitee_id,
                status="pending",
                was_member_before=False,
                created_at=utcnow(),
            ),
        ])
        # Seed 4 already-confirmed referrals so invitee makes 5 -> mints REF20 coupon
        for i in range(4):
            fid = 70100 + i
            session.add(User(telegram_id=fid, name=f"F{i}", first_seen=utcnow(), last_seen=utcnow()))
            session.add(
                Referral(
                    referrer_id=referrer_id,
                    invitee_id=fid,
                    status="confirmed",
                    was_member_before=False,
                    created_at=utcnow(),
                    confirmed_at=utcnow(),
                )
            )
        await session.commit()

    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(channel_member_router)

    tg_invitee = TgUser(id=invitee_id, is_bot=False, first_name="Invitee")
    tg_actor = TgUser(id=invitee_id, is_bot=False, first_name="Invitee")
    tg_chat = Chat(id=channel_id, type="channel", title="Moonlight Chinese Shop")

    mock_bot = AsyncMock()
    mock_bot.id = 9277851759
    mock_bot.get_me = AsyncMock(return_value=SimpleNamespace(id=9277851759, username="moonlight_chinese_bot"))
    mock_bot.get_chat_member = AsyncMock(return_value=SimpleNamespace(status="member"))
    mock_bot.send_message = AsyncMock()

    join_update = Update(
        update_id=5001,
        chat_member=ChatMemberUpdated(
            chat=tg_chat,
            from_user=tg_actor,
            date=1700000000,
            old_chat_member=ChatMemberLeft(user=tg_invitee),
            new_chat_member=ChatMemberMember(user=tg_invitee),
        ),
    )

    with patch("bot.handlers.channel_member.async_session_factory", test_db_session), \
         patch("bot.services.contest_service.async_session_factory", test_db_session, create=True):
        await dp.feed_update(mock_bot, join_update)

        async with test_db_session() as session:
            ref = (await session.execute(select(Referral).where(Referral.invitee_id == invitee_id))).scalars().first()
            assert ref.status == "confirmed"
            rc = (await session.execute(select(ReferralCoupon).where(ReferralCoupon.user_id == referrer_id))).scalars().first()
            assert rc is not None and rc.milestone == 5
            promo = (await session.execute(select(PromoCode).where(PromoCode.code == rc.code))).scalars().first()
            assert promo.is_active is True

            # User clicking Tasdiqlash 0.1s later must NOT hit 3s throttle
            click_res = await confirm_referral(
                session=session,
                bot=mock_bot,
                invitee_id=invitee_id,
                referrer_id=referrer_id,
                bot_username="moonlight_chinese_bot",
            )
            assert click_res["status"] == "success"

        leave_update = Update(
            update_id=5002,
            chat_member=ChatMemberUpdated(
                chat=tg_chat,
                from_user=tg_actor,
                date=1700000010,
                old_chat_member=ChatMemberMember(user=tg_invitee),
                new_chat_member=ChatMemberLeft(user=tg_invitee),
            ),
        )
        await dp.feed_update(mock_bot, leave_update)

    async with test_db_session() as session:
        ref_after = (await session.execute(select(Referral).where(Referral.invitee_id == invitee_id))).scalars().first()
        assert ref_after.status == "revoked"
        promo_after = (await session.execute(select(PromoCode).where(PromoCode.code == rc.code))).scalars().first()
        assert promo_after.is_active is False


@pytest.mark.asyncio
async def test_channel_my_chat_member_group_security_and_demotion(test_db_session):
    """
    1. Non-owner promoting bot in a group must NOT overwrite Setting.chat_id.
    2. Owner promoting bot in a group DOES update Setting.chat_id.
    3. Demoting the bot in the linked channel pauses active Contest and notifies owners.
    """
    from bot.handlers.channel import handle_bot_chat_member_update

    owner_id = 111222
    stranger_id = 999888
    channel_id = -100444555666

    async with test_db_session() as session:
        session.add(Admin(telegram_id=owner_id, name="Owner", role="owner"))
        ch_set = (await session.execute(select(Setting).where(Setting.key == "channel_id"))).scalars().first()
        ch_set.value = str(channel_id)
        session.add(Setting(key="chat_id", value="-1003565030513"))
        session.add(
            Contest(
                prize_1="P1",
                prize_2="P2",
                prize_3="P3",
                status="active",
                ends_at=utcnow() + timedelta(days=3),
            )
        )
        await session.commit()

    bot_user = TgUser(id=9277851759, is_bot=True, first_name="Bot")
    group_chat = Chat(id=-100999000111, type="supergroup", title="Stranger Group")
    fake_admin_member = ChatMemberAdministrator(
        user=bot_user,
        can_be_edited=False,
        is_anonymous=False,
        can_manage_chat=True,
        can_delete_messages=True,
        can_manage_video_chats=True,
        can_restrict_members=True,
        can_promote_members=True,
        can_change_info=True,
        can_invite_users=True,
        can_post_stories=False,
        can_edit_stories=False,
        can_delete_stories=False,
        can_send_welcome_messages=False,
    )

    mock_bot = AsyncMock()
    with patch("bot.handlers.channel.async_session_factory", test_db_session), \
         patch("bot.handlers.channel.bot", mock_bot):
        # 1. Stranger adds bot to group -> ignored
        stranger_event = ChatMemberUpdated(
            chat=group_chat,
            from_user=TgUser(id=stranger_id, is_bot=False, first_name="Stranger"),
            date=1700000000,
            old_chat_member=ChatMemberLeft(user=bot_user),
            new_chat_member=fake_admin_member,
        )
        await handle_bot_chat_member_update(stranger_event)

        async with test_db_session() as session:
            chat_row = (await session.execute(select(Setting).where(Setting.key == "chat_id"))).scalars().first()
            assert chat_row.value == "-1003565030513"

        # 2. Owner adds bot to group -> updates chat_id
        owner_group = Chat(id=-100777666555, type="supergroup", title="Official Chat")
        owner_event = ChatMemberUpdated(
            chat=owner_group,
            from_user=TgUser(id=owner_id, is_bot=False, first_name="Owner"),
            date=1700000001,
            old_chat_member=ChatMemberLeft(user=bot_user),
            new_chat_member=fake_admin_member,
        )
        await handle_bot_chat_member_update(owner_event)

        async with test_db_session() as session:
            chat_row2 = (await session.execute(select(Setting).where(Setting.key == "chat_id"))).scalars().first()
            assert chat_row2.value == "-100777666555"

        # 3. Bot demoted in linked channel -> contest paused + owner alerted
        ch_chat = Chat(id=channel_id, type="channel", title="Moonlight")
        demote_event = ChatMemberUpdated(
            chat=ch_chat,
            from_user=TgUser(id=owner_id, is_bot=False, first_name="Owner"),
            date=1700000002,
            old_chat_member=fake_admin_member,
            new_chat_member=ChatMemberMember(user=bot_user),
        )
        await handle_bot_chat_member_update(demote_event)

    async with test_db_session() as session:
        contest = (await session.execute(select(Contest))).scalars().first()
        assert contest.status == "paused"
    assert mock_bot.send_message.called
    assert mock_bot.send_message.call_args.kwargs["chat_id"] == owner_id


@pytest.mark.asyncio
async def test_boost_title_stripping_vision_thinking_parts_and_colors():
    """
    1. /boost and /boost@bot never leak 'Boost' as product title.
    2. Gemini thinking parts (thought=True) are skipped in favor of JSON answer part.
    3. Uzbek-Russian color transliterations normalize cleanly and drop noise tokens.
    """
    from api.services.formatters import parse_channel_post
    from api.services.vision_ocr import extract_product_from_image, normalize_colors

    res1 = parse_channel_post("/boost 50 yuan", apply_margin=True)
    assert res1["title"].lower() != "boost"
    assert res1["title"] == "Mahsulot 🌸"
    assert res1["source_price"] == 90000

    res2 = parse_channel_post("/boost@moonlight_chinese_bot #scarf 30 yuan", apply_margin=True)
    assert res2["title"] == "Scarf 🌸"

    # Mock Gemini response with a thought=True part before JSON part
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {"thought": True, "text": "Let me think step by step about this scarf."},
                        {
                            "text": '{"title": "Yurakchali Issiq Sharf 🌸", "category": "scarf", "source_price": 30, "currency": "CNY", "sizes": ["Standart"], "colors": ["Qizil", "Bej"], "is_spec_screenshot": false}'
                        },
                    ]
                }
            }
        ]
    }
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("api.services.vision_ocr.settings.GEMINI_API_KEY", "test_gemini_key"), \
         patch("api.services.vision_ocr.httpx.AsyncClient", return_value=mock_client):
        v_res = await extract_product_from_image(b"fake_image_bytes")
        assert v_res["success"] is True
        assert v_res["title"] == "Yurakchali Issiq Sharf"
        assert v_res["category"] == "scarf"

    colors = normalize_colors(["Malina rang", "Svet", "Yashil", "Seriy", "Balotiviy"])
    assert "Kulrang 🩶" in colors
    assert "Bolotniy 💚" in colors
    assert all("Svet" not in c for c in colors)


@pytest.mark.asyncio
async def test_start_reply_keyboard_subscription_bypass_and_escaping(test_db_session):
    """
    1. send_welcome_greeting still sends get_main_reply_keyboard() even when banner exists.
    2. Non-subscriber sending /start ref_0 or /start r_invalid is stopped by subscription prompt.
    3. send_product_deep_link HTML-escapes <script>& in description.
    """
    from bot.handlers.start import handle_start, send_product_deep_link, send_welcome_greeting
    from bot.keyboards.reply import REFERRAL_BUTTON_TEXT

    # 1. Welcome greeting sends both photo + reply keyboard follow-up
    welcome_msg = MagicMock(spec=Message)
    welcome_msg.answer_photo = AsyncMock()
    welcome_msg.answer = AsyncMock()

    with patch("bot.handlers.start.async_session_factory", test_db_session), \
         patch.object(Path, "is_file", return_value=True):
        await send_welcome_greeting(welcome_msg, 12345)

    assert welcome_msg.answer_photo.called
    assert welcome_msg.answer.called
    kb = welcome_msg.answer.call_args.kwargs.get("reply_markup")
    kb_texts = [btn.text for row in kb.keyboard for btn in row]
    assert REFERRAL_BUTTON_TEXT in kb_texts

    # 2. Subscription gate blocks /start ref_0 and /start r_invalid for non-subscribers
    async with test_db_session() as session:
        ch = (await session.execute(select(Setting).where(Setting.key == "channel_id"))).scalars().first()
        ch.value = "-1004378811161"
        await session.commit()

    for bad_arg in ("ref_0", "r_invalid"):
        msg = MagicMock(spec=Message)
        msg.from_user = TgUser(id=880011, is_bot=False, first_name="Guest", username="guest")
        msg.bot = AsyncMock()
        msg.answer = AsyncMock()
        msg.answer_photo = AsyncMock()
        cmd = CommandObject(prefix="/", command="start", args=bad_arg)

        with patch("bot.handlers.start.async_session_factory", test_db_session), \
             patch("bot.handlers.start.check_dual_subscription", AsyncMock(return_value=(False, False, "https://t.me/c", "https://t.me/g"))):
            await handle_start(msg, cmd)

        assert msg.answer.called
        assert not msg.answer_photo.called
        assert "a'zo bo'ling" in msg.answer.call_args.args[0].lower()

    # 3. HTML escaping in send_product_deep_link
    async with test_db_session() as session:
        session.add(
            Product(
                id=888,
                title="Test Scarf",
                description="Material <100%> & silk",
                price=50000,
                category="scarf",
                photos=[],
                sizes=["Standart"],
            )
        )
        await session.commit()

    prod_msg = MagicMock(spec=Message)
    prod_msg.answer = AsyncMock()
    prod_msg.answer_photo = AsyncMock()
    with patch("bot.handlers.start.async_session_factory", test_db_session):
        ok = await send_product_deep_link(prod_msg, 888)
    assert ok is True
    sent_html = prod_msg.answer.call_args.args[0]
    assert "&lt;100%&gt; &amp; silk" in sent_html


@pytest.mark.asyncio
async def test_order_cancel_restores_coupon_and_blocks_invalid_transitions(client, test_db_session):
    """
    1. Bot order_cancel restores ReferralCoupon & decrements PromoCode, keeping is_active=False when referrals < milestone.
    2. Bot order_accept refuses already-cancelled order; order_cancel refuses already-accepted order.
    3. API PATCH /api/admin/orders/{id}/status blocks accepted->pending_approval & cancelled->accepted and returns full OrderOut.
    """
    from bot.handlers.orders import handle_order_accept, handle_order_cancel

    admin_id = 8643984824
    cust_id = 60001
    async with test_db_session() as session:
        session.add(Admin(telegram_id=admin_id, name="Otabek", role="owner"))
        session.add(User(telegram_id=cust_id, name="Cust", cashback_balance=5000))
        # Seed only 4 confirmed referrals (< milestone 5) so coupon should stay locked in PromoCode after cancel
        for i in range(4):
            fid = 60100 + i
            session.add(User(telegram_id=fid, name=f"F{i}", first_seen=utcnow(), last_seen=utcnow()))
            session.add(Referral(referrer_id=cust_id, invitee_id=fid, status="confirmed", created_at=utcnow()))

        order = Order(
            user_id=cust_id,
            customer_name="Cust",
            items_snapshot=[{"product_id": 1, "title": "Jempir", "price": 99000, "qty": 1}],
            total=74200,
            cashback_used=5000,
            promo_code="REF20-AAAA-BBBB",
            discount_amount=19800,
            status="pending_approval",
        )
        session.add(order)
        await session.flush()

        rc = ReferralCoupon(
            user_id=cust_id,
            code="REF20-AAAA-BBBB",
            discount_percent=20,
            milestone=5,
            is_used=True,
            used_at=utcnow(),
            order_id=order.id,
            product_id=1,
            discount_amount=19800,
            created_at=utcnow(),
        )
        promo = PromoCode(
            code="REF20-AAAA-BBBB",
            discount_percent=20,
            max_uses=1,
            used_count=1,
            is_active=False,
        )
        session.add_all([rc, promo])

        accepted_order = Order(
            user_id=cust_id,
            customer_name="Cust",
            items_snapshot=[{"product_id": 1, "title": "Jempir", "price": 99000, "qty": 1}],
            total=99000,
            status="accepted",
        )
        session.add(accepted_order)
        await session.commit()
        order_id = order.id
        acc_id = accepted_order.id

    cb = MagicMock(spec=CallbackQuery)
    cb.data = f"order_cancel_{order_id}"
    cb.from_user = TgUser(id=admin_id, is_bot=False, first_name="Otabek")
    cb.answer = AsyncMock()
    cb.message = MagicMock(spec=Message)
    cb.message.caption = None
    cb.message.photo = None
    cb.message.document = None
    cb.message.text = f"Buyurtma #{order_id}"
    cb.message.html_text = f"Buyurtma #{order_id}"
    cb.message.edit_text = AsyncMock()

    mock_bot = AsyncMock()
    with patch("bot.handlers.orders.bot", mock_bot), \
         patch("bot.handlers.orders.async_session_factory", test_db_session):
        await handle_order_cancel(cb)

        async with test_db_session() as session:
            o = (await session.execute(select(Order).where(Order.id == order_id))).scalars().first()
            assert o.status == "cancelled"
            u = (await session.execute(select(User).where(User.telegram_id == cust_id))).scalars().first()
            assert u.cashback_balance == 10000
            rc_db = (await session.execute(select(ReferralCoupon).where(ReferralCoupon.code == "REF20-AAAA-BBBB"))).scalars().first()
            assert rc_db.is_used is False
            assert rc_db.order_id is None
            assert rc_db.product_id is None
            assert rc_db.discount_amount == 0
            p_db = (await session.execute(select(PromoCode).where(PromoCode.code == "REF20-AAAA-BBBB"))).scalars().first()
            assert p_db.used_count == 0
            # Referrer only has 4 confirmed friends (<5), so PromoCode stays inactive!
            assert p_db.is_active is False

        # Refuses accepting cancelled order
        cb_acc = MagicMock(spec=CallbackQuery)
        cb_acc.data = f"order_accept_{order_id}"
        cb_acc.from_user = TgUser(id=admin_id, is_bot=False, first_name="Otabek")
        cb_acc.answer = AsyncMock()
        await handle_order_accept(cb_acc)
        assert "bekor qilingan" in cb_acc.answer.call_args.args[0].lower()

        # Refuses cancelling accepted order
        cb_can_acc = MagicMock(spec=CallbackQuery)
        cb_can_acc.data = f"order_cancel_{acc_id}"
        cb_can_acc.from_user = TgUser(id=admin_id, is_bot=False, first_name="Otabek")
        cb_can_acc.answer = AsyncMock()
        await handle_order_cancel(cb_can_acc)
        assert "qabul qilingan" in cb_can_acc.answer.call_args.args[0].lower()

    # API checks: full OrderOut + blocked transitions
    admin_init = generate_test_init_data(user_id=admin_id, first_name="Otabek")
    list_resp = await client.get("/api/admin/orders", headers={"X-Telegram-Init-Data": admin_init})
    assert list_resp.status_code == 200
    first_item = next(x for x in list_resp.json() if x["id"] == order_id)
    assert first_item["promo_code"] == "REF20-AAAA-BBBB"
    assert first_item["discount_amount"] == 19800
    assert first_item["cashback_used"] == 5000
    assert "cargo_stage" in first_item

    bad1 = await client.patch(
        f"/api/admin/orders/{acc_id}/status",
        json={"status": "pending_approval"},
        headers={"X-Telegram-Init-Data": admin_init},
    )
    assert bad1.status_code == 400

    bad2 = await client.patch(
        f"/api/admin/orders/{order_id}/status",
        json={"status": "accepted"},
        headers={"X-Telegram-Init-Data": admin_init},
    )
    assert bad2.status_code == 400


@pytest.mark.asyncio
async def test_api_orders_price_tampering_cashback_and_promo_checks(client, test_db_session):
    """
    1. Client passing tampered price=1 for DB Product #1 (99000) is charged 99000.
    2. Negative qty/price rejected with 400.
    3. validate_and_calculate_coupon_discount enforces min_order_amount & handles naive valid_until.
    4. get_user_referral_stats skips already-used milestone 5 -> next_milestone=10, friends_needed=6.
    """
    from bot.services.referral_service import get_user_referral_stats, validate_and_calculate_coupon_discount

    uid = 777111
    async with test_db_session() as session:
        session.add(User(telegram_id=uid, name="Shopper", cashback_balance=50000))
        for i in range(4):
            fid = 777200 + i
            session.add(User(telegram_id=fid, name=f"F{i}", first_seen=utcnow(), last_seen=utcnow()))
            session.add(Referral(referrer_id=uid, invitee_id=fid, status="confirmed", created_at=utcnow()))
        session.add(
            ReferralCoupon(
                user_id=uid,
                code="REF20-USED-M5",
                discount_percent=20,
                milestone=5,
                is_used=True,
                used_at=utcnow(),
                created_at=utcnow(),
            )
        )
        session.add(
            PromoCode(
                code="MIN300",
                discount_percent=10,
                min_order_amount=300000,
                max_uses=5,
                used_count=0,
                is_active=True,
                # Naive UTC datetime intentionally
                valid_until=(datetime.now(timezone.utc) + timedelta(days=5)).replace(tzinfo=None),
            )
        )
        await session.commit()

        # PromoCode checks
        res_min = await validate_and_calculate_coupon_discount(
            session, uid, "MIN300", [{"product_id": 1, "price": 99000, "qty": 1}]
        )
        assert res_min["valid"] is False
        assert "300 000" in res_min["message"]

        res_ok = await validate_and_calculate_coupon_discount(
            session, uid, "MIN300", [{"product_id": 1, "price": 99000, "qty": 4}]
        )
        assert res_ok["valid"] is True

        stats = await get_user_referral_stats(session, uid, "moonlight_chinese_bot")
        assert stats["confirmed_count"] == 4
        assert stats["next_milestone"] == 10
        assert stats["friends_needed_for_next"] == 6

    headers = {"X-Telegram-Init-Data": generate_test_init_data(user_id=uid, first_name="Shopper")}
    with patch("api.routes.orders.send_payment_instructions"):
        # Tampered price for product_id=1 must be ignored in favor of 99000
        resp = await client.post(
            "/api/orders",
            json={"items": [{"product_id": 1, "title": "Hack", "price": 1, "qty": 1}], "use_cashback": 0},
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["total"] == 99000

        # Negative custom price rejected
        bad_price = await client.post(
            "/api/orders",
            json={"items": [{"title": "Custom", "price": -500, "qty": 1}], "use_cashback": 0},
            headers=headers,
        )
        assert bad_price.status_code == 400


@pytest.mark.asyncio
async def test_admin_settings_security_and_public_settings_resilience(client, test_db_session):
    """
    1. Plain admin GET /api/admin/settings hides owner_invite_code.
    2. Plain admin POST /api/admin/settings rejects owner_invite_code (403), channel_id (403), bad cargo_rate (400).
    3. Public GET /api/settings survives non-numeric cargo_rate without 500 error.
    """
    plain_admin_id = 334455
    async with test_db_session() as session:
        session.add(Admin(telegram_id=plain_admin_id, name="Helper", role="admin"))
        session.add(Setting(key="owner_invite_code", value="TOP_SECRET_TOKEN"))
        await session.commit()

    headers = {"X-Telegram-Init-Data": generate_test_init_data(user_id=plain_admin_id, first_name="Helper")}
    get_resp = await client.get("/api/admin/settings", headers=headers)
    assert get_resp.status_code == 200
    assert "owner_invite_code" not in get_resp.json()
    assert "owner_claimed_at" not in get_resp.json()

    r1 = await client.post("/api/admin/settings", json={"owner_invite_code": "evil"}, headers=headers)
    assert r1.status_code == 403

    r2 = await client.post("/api/admin/settings", json={"channel_id": "-100111"}, headers=headers)
    assert r2.status_code == 403

    r3 = await client.post("/api/admin/settings", json={"cargo_rate": "abc"}, headers=headers)
    assert r3.status_code == 400

    # Corrupt DB cargo_rate safely handled by public /api/settings
    async with test_db_session() as session:
        cr = (await session.execute(select(Setting).where(Setting.key == "cargo_rate"))).scalars().first()
        cr.value = "not_a_number"
        await session.commit()

    pub = await client.get("/api/settings")
    assert pub.status_code == 200
    assert pub.json()["cargo_rate"] == 10000


@pytest.mark.asyncio
async def test_receipt_notifier_inline_dilemma_dead_buttons_and_contest_edit(test_db_session):
    """
    1. notify_admins_new_receipt keeps HTML valid and <= 1020 chars on long item titles with <>& and includes coupon line.
    2. handle_dilemma_vote calls callback.bot.edit_message_reply_markup(inline_message_id=...).
    3. handle_toggle_badges toggles product badges.
    4. handle_dq_specific_user enters ContestDisqualifyState.reason.
    5. save_edited_prizes preserves reply_markup on channel announcement edit.
    6. recover_abandoned_carts does not advertise unseeded MOON10 promo code.
    """
    from bot.handlers.admin import handle_toggle_badges
    from bot.handlers.admin_contest import ContestDisqualifyState, handle_dq_specific_user, save_edited_prizes
    from bot.handlers.inline import handle_dilemma_vote
    from bot.services.cart_recovery import recover_abandoned_carts
    from bot.services.order_notifier import notify_admins_new_receipt

    admin_id = 8643984824
    async with test_db_session() as session:
        ch = (await session.execute(select(Setting).where(Setting.key == "channel_id"))).scalars().first()
        ch.value = "-1004378811161"
        session.add(Admin(telegram_id=admin_id, name="Otabek", role="owner"))
        session.add(User(telegram_id=9901, name="Mijoz", first_seen=utcnow(), last_seen=utcnow()))
        session.add(
            CartItem(
                user_id=9901,
                product_id=1,
                qty=1,
                created_at=utcnow() - timedelta(hours=3),
            )
        )
        long_items = [
            {"title": f"<Very> & Long Product Name {i} " + ("X" * 90), "qty": 2, "price": 100000}
            for i in range(5)
        ]
        long_order = Order(
            user_id=9901,
            customer_name="O' <Test> & Name",
            items_snapshot=long_items,
            total=160000,
            promo_code="REF20-XXXX-YYYY",
            discount_amount=40000,
            status="pending_approval",
            receipt_photo_id="receipt_long_id",
        )
        session.add(long_order)
        c = Contest(
            prize_1="Old 1",
            prize_2="Old 2",
            prize_3="Old 3",
            status="active",
            channel_message_id=4242,
            ends_at=utcnow() + timedelta(days=2),
        )
        session.add(c)
        await session.commit()
        long_order_id = long_order.id
        contest_id = c.id

    # 1. Receipt notifier long HTML + coupon
    mock_notifier_bot = AsyncMock()
    with patch("bot.services.order_notifier.async_session_factory", test_db_session), \
         patch("bot.services.order_notifier.bot", mock_notifier_bot):
        await notify_admins_new_receipt(long_order_id)
    assert mock_notifier_bot.send_photo.called
    cap = mock_notifier_bot.send_photo.call_args.kwargs["caption"]
    assert len(cap) <= 1020
    assert "REF20-XXXX-YYYY" in cap
    assert "40.000" in cap

    # 2. Inline dilemma vote uses bot.edit_message_reply_markup
    vote_cb = MagicMock(spec=CallbackQuery)
    vote_cb.data = "vote:1:0:0:1:1"
    vote_cb.inline_message_id = "inline_msg_abc"
    vote_cb.message = None
    vote_cb.answer = AsyncMock()
    vote_cb.bot = AsyncMock()
    vote_cb.bot.get_me = AsyncMock(return_value=SimpleNamespace(username="moonlight_chinese_bot"))
    vote_cb.bot.edit_message_reply_markup = AsyncMock()
    with patch("bot.handlers.inline.bot", vote_cb.bot):
        await handle_dilemma_vote(vote_cb)
    vote_cb.bot.edit_message_reply_markup.assert_awaited_once()
    assert vote_cb.bot.edit_message_reply_markup.call_args.kwargs["inline_message_id"] == "inline_msg_abc"

    # 3. Dead button fix: admin_toggle_badges_1
    badge_cb = MagicMock(spec=CallbackQuery)
    badge_cb.data = "admin_toggle_badges_1"
    badge_cb.from_user = TgUser(id=admin_id, is_bot=False, first_name="Otabek")
    badge_cb.answer = AsyncMock()
    badge_cb.message = MagicMock(spec=Message)
    badge_cb.message.edit_text = AsyncMock()
    with patch("bot.handlers.admin.async_session_factory", test_db_session):
        await handle_toggle_badges(badge_cb)
    async with test_db_session() as session:
        p1 = (await session.execute(select(Product).where(Product.id == 1))).scalars().first()
        assert p1.is_hit is True and p1.is_new is True

    # 4. Dead button fix: adm_c_dq_user:<cid>:<uid>
    dq_cb = MagicMock(spec=CallbackQuery)
    dq_cb.data = f"adm_c_dq_user:{contest_id}:9901"
    dq_cb.from_user = TgUser(id=admin_id, is_bot=False, first_name="Otabek")
    dq_cb.answer = AsyncMock()
    dq_cb.message = MagicMock(spec=Message)
    dq_cb.message.answer = AsyncMock()
    dq_state = AsyncMock()
    with patch("bot.handlers.admin_contest.async_session_factory", test_db_session):
        await handle_dq_specific_user(dq_cb, dq_state)
    dq_state.set_state.assert_awaited_once_with(ContestDisqualifyState.reason)
    dq_state.update_data.assert_awaited_once_with(contest_id=contest_id, dq_user_id=9901)

    # 5. Contest prize edit preserves channel [🎁 Qatnashish] button
    edit_msg = MagicMock(spec=Message)
    edit_msg.answer = AsyncMock()
    edit_msg.bot = AsyncMock()
    edit_msg.bot.get_me = AsyncMock(return_value=SimpleNamespace(username="moonlight_chinese_bot"))
    edit_msg.bot.edit_message_text = AsyncMock()
    edit_state = AsyncMock()
    edit_state.get_data = AsyncMock(return_value={"contest_id": contest_id, "p1": "New 1", "p2": "New 2", "p3": "New 3"})
    with patch("bot.handlers.admin_contest.async_session_factory", test_db_session):
        await save_edited_prizes(edit_msg, edit_state, [])
    edit_msg.bot.edit_message_text.assert_awaited_once()
    rm = edit_msg.bot.edit_message_text.call_args.kwargs.get("reply_markup")
    assert rm is not None
    assert rm.inline_keyboard[0][0].text == "🎁 Qatnashish"

    # 6. Cart recovery does not advertise unseeded MOON10
    cr_bot = AsyncMock()
    with patch("bot.services.cart_recovery.async_session_factory", test_db_session):
        sent = await recover_abandoned_carts(cr_bot)
    assert sent == 1
    assert "MOON10" not in cr_bot.send_message.call_args.kwargs["text"]
