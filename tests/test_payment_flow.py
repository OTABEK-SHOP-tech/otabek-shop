import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from sqlalchemy import select
from aiogram.types import Message, CallbackQuery, User as TgUser, Chat, PhotoSize, Document

from db.models import Order, User, Admin, Setting
from db.session import _add_missing_columns
from bot.services.order_notifier import (
    send_payment_instructions,
    notify_admins_new_receipt,
    broadcast_live_order_proof,
)
from bot.handlers.orders import handle_receipt_upload, handle_order_accept, handle_order_cancel
from tests.conftest import generate_test_init_data


@pytest.mark.asyncio
async def test_order_creation_status_is_awaiting_receipt(client, test_db_session):
    """Verifies that creating an order sets status to awaiting_receipt."""
    async_session = test_db_session
    user_id = 99881122

    user_init = generate_test_init_data(user_id=user_id, first_name="Gulnoza")

    # Order payload
    payload = {
        "items": [
            {
                "product_id": 1,
                "title": "Aesthetic Jempir 🌸",
                "price": 99000,
                "qty": 1,
                "size": "M",
                "color": "Pushti 🌸",
            }
        ],
        "use_cashback": 0,
    }

    with patch("api.routes.orders.send_payment_instructions") as mock_send_instructions:
        resp = await client.post("/api/orders", json=payload, headers={"X-Telegram-Init-Data": user_init})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "awaiting_receipt"
        assert data["receipt_photo_id"] is None
        assert data["total"] == 99000

        # Check DB
        async with async_session() as session:
            db_order = (await session.execute(select(Order).where(Order.id == data["id"]))).scalars().first()
            assert db_order is not None
            assert db_order.status == "awaiting_receipt"
            assert db_order.receipt_photo_id is None


@pytest.mark.asyncio
async def test_send_payment_instructions_only_notifies_customer(test_db_session):
    """
    Verifies that payment instructions are sent to the customer ONLY.
    Admins are NOT contacted at this step.
    """
    async_session = test_db_session
    customer_id = 77112233

    mock_bot = AsyncMock()
    with patch("bot.services.order_notifier.bot", mock_bot), \
         patch("bot.services.order_notifier.async_session_factory", async_session):

        await send_payment_instructions(
            order_id=101,
            user_id=customer_id,
            customer_name="Nargiza",
            items=[{"title": "Pushti Jempir", "price": 99000, "qty": 1}],
            total=99000,
            estimated_cargo=24000,
        )

        # Bot must have been called exactly once: to customer_id
        assert mock_bot.send_message.call_count == 1
        call_kwargs = mock_bot.send_message.call_args.kwargs
        assert call_kwargs["chat_id"] == customer_id
        text = call_kwargs["text"]
        assert "99.000 so'm" in text
        assert "to'lov chekini" in text.lower()
        assert "Chekni yubormaguningizcha buyurtmangiz adminlarga yuborilmaydi" in text
        assert "9860" in text or "karta" in text.lower()


@pytest.mark.asyncio
async def test_receipt_photo_upload_flow(test_db_session):
    """
    Customer sends a photo receipt.
    Handler updates order to pending_approval, sets receipt_photo_id,
    confirms to customer, and alerts admins.
    """
    async_session = test_db_session
    customer_id = 66554433

    # Seed an awaiting_receipt order
    async with async_session() as session:
        session.add(User(telegram_id=customer_id, name="Malika"))
        order = Order(
            user_id=customer_id,
            customer_name="Malika",
            customer_username="malika_m",
            items_snapshot=[{"title": "Parik 💇‍♀️", "price": 125000, "qty": 1}],
            total=125000,
            status="awaiting_receipt",
        )
        session.add(order)
        await session.commit()
        order_id = order.id

    mock_message = MagicMock(spec=Message)
    mock_message.from_user = TgUser(id=customer_id, is_bot=False, first_name="Malika", username="malika_m")
    mock_message.chat = Chat(id=customer_id, type="private")
    mock_message.document = None

    # Simulate highest-resolution photo
    mock_photo = PhotoSize(file_id="receipt_photo_file_12345", file_unique_id="u123", width=800, height=1200)
    mock_message.photo = [mock_photo]
    mock_message.answer = AsyncMock()

    mock_state = AsyncMock()
    mock_state.get_state.return_value = None

    with patch("bot.handlers.orders.async_session_factory", async_session), \
         patch("bot.services.order_notifier.async_session_factory", async_session), \
         patch("bot.services.order_notifier.bot") as mock_bot:

        mock_bot.send_photo = AsyncMock()
        mock_bot.send_message = AsyncMock()

        await handle_receipt_upload(mock_message, mock_state)

        # 1. Customer received confirmation
        mock_message.answer.assert_called_once()
        ans_text = mock_message.answer.call_args.args[0]
        assert "To'lov chekingiz qabul qilindi" in ans_text
        assert "Adminlar tekshirmoqda" in ans_text

        # 2. DB updated
        async with async_session() as session:
            updated_order = (await session.execute(select(Order).where(Order.id == order_id))).scalars().first()
            assert updated_order.status == "pending_approval"
            assert updated_order.receipt_photo_id == "receipt_photo_file_12345"

        # 3. Admins alerted with receipt photo and styled buttons
        assert mock_bot.send_photo.called
        admin_call_kwargs = mock_bot.send_photo.call_args.kwargs
        assert admin_call_kwargs["photo"] == "receipt_photo_file_12345"
        assert f"#{order_id}" in admin_call_kwargs["caption"]
        assert "125.000 so'm" in admin_call_kwargs["caption"]

        markup = admin_call_kwargs["reply_markup"]
        buttons = [btn for row in markup.inline_keyboard for btn in row]
        accept_btn = next((b for b in buttons if b.callback_data == f"order_accept_{order_id}"), None)
        cancel_btn = next((b for b in buttons if b.callback_data == f"order_cancel_{order_id}"), None)
        profile_btn = next((b for b in buttons if b.url and "malika_m" in b.url), None)

        assert accept_btn is not None
        assert accept_btn.style == "success"
        assert cancel_btn is not None
        assert cancel_btn.style == "danger"
        assert profile_btn is not None
        assert profile_btn.style == "primary"


@pytest.mark.asyncio
async def test_admin_accept_order_awards_cashback_and_proof(test_db_session):
    """
    Admin clicks accept:
    - Order status becomes accepted
    - Customer gets 2% cashback
    - Customer notified with Moonlight Shop Admin contact button
    - Social proof broadcasted to @moonlight_shop_otzv
    - Admin message edited
    """
    async_session = test_db_session
    admin_id = 8643984824  # Otabek
    customer_id = 99118822

    async with async_session() as session:
        session.add(Admin(telegram_id=admin_id, name="Otabek", role="owner"))
        session.add(User(telegram_id=customer_id, name="Zilola", cashback_balance=1000))
        order = Order(
            user_id=customer_id,
            customer_name="Zilola",
            customer_username="zilola_z",
            items_snapshot=[{"title": "Lolita Wig 💇‍♀️", "price": 100000, "qty": 1}],
            total=100000,
            status="pending_approval",
            receipt_photo_id="receipt_abc",
        )
        session.add(order)
        await session.commit()
        order_id = order.id

    mock_callback = MagicMock(spec=CallbackQuery)
    mock_callback.data = f"order_accept_{order_id}"
    mock_callback.from_user = TgUser(id=admin_id, is_bot=False, first_name="Otabek")
    mock_callback.answer = AsyncMock()

    mock_message = MagicMock(spec=Message)
    mock_message.photo = [PhotoSize(file_id="receipt_abc", file_unique_id="u", width=100, height=100)]
    mock_message.caption = f"Buyurtma #{order_id}"
    mock_message.html_text = f"Buyurtma #{order_id}"
    mock_message.edit_caption = AsyncMock()
    mock_message.edit_text = AsyncMock()
    mock_callback.message = mock_message

    mock_bot = AsyncMock()
    with patch("bot.handlers.orders.bot", mock_bot), \
         patch("bot.handlers.orders.async_session_factory", async_session), \
         patch("bot.services.order_notifier.bot", mock_bot), \
         patch("bot.services.order_notifier.async_session_factory", async_session):

        await handle_order_accept(mock_callback)

        # 1. Check order status & cashback
        async with async_session() as session:
            o = (await session.execute(select(Order).where(Order.id == order_id))).scalars().first()
            assert o.status == "accepted"

            u = (await session.execute(select(User).where(User.telegram_id == customer_id))).scalars().first()
            # 2% of 100000 is 2000; initial 1000 -> 3000
            assert u.cashback_balance == 3000

        # 2. Customer notified with Moonlight Shop Admin contact button
        mock_bot.send_message.assert_called()
        customer_calls = [
            c for c in mock_bot.send_message.call_args_list
            if c.kwargs.get("chat_id") == customer_id
        ]
        assert len(customer_calls) >= 1
        c_kwargs = customer_calls[0].kwargs
        assert "to'lovingiz tasdiqlandi" in c_kwargs["text"].lower() or "qabul qilindi" in c_kwargs["text"].lower()
        btn = c_kwargs["reply_markup"].inline_keyboard[0][0]
        assert "MOONLIGHT_ADMINNN" in btn.url or "t.me/" in btn.url

        # 3. Admin message caption edited
        mock_message.edit_caption.assert_called_once()
        assert "QABUL QILINDI" in mock_message.edit_caption.call_args.kwargs["caption"]

        # 4. Callback answered
        mock_callback.answer.assert_called_once()

        # 5. Proof broadcasted to otziv channel with Admin Contact button
        channel_calls = [
            c for c in mock_bot.send_message.call_args_list
            if c.kwargs.get("chat_id") == -1004297799216 or "Yangi Xarid" in c.kwargs.get("text", "")
        ]
        assert len(channel_calls) >= 1
        proof_call = channel_calls[0]
        assert "Moonlight Alerts" in proof_call.kwargs["text"]
        assert "Yangi Xarid" in proof_call.kwargs["text"]
        assert "100.000 so'm" in proof_call.kwargs["text"]

        proof_markup = proof_call.kwargs["reply_markup"]
        proof_buttons = [btn for row in proof_markup.inline_keyboard for btn in row]
        contact_admin_btn = next((b for b in proof_buttons if "MOONLIGHT_ADMINNN" in (b.url or "") or "bog'lanish" in b.text.lower()), None)
        assert contact_admin_btn is not None
        assert "Adminga bog'lanish" in contact_admin_btn.text


@pytest.mark.asyncio
async def test_admin_cancel_order_refunds_cashback(test_db_session):
    """
    Admin clicks cancel:
    - Order status becomes cancelled
    - Cashback used during checkout is refunded
    - Customer notified with reason and Moonlight Shop Admin link
    - Admin message edited
    """
    async_session = test_db_session
    admin_id = 8413799379  # Gulmira opa
    customer_id = 33445566

    async with async_session() as session:
        session.add(Admin(telegram_id=admin_id, name="Gulmira", role="owner"))
        session.add(User(telegram_id=customer_id, name="Rayhona", cashback_balance=5000))
        order = Order(
            user_id=customer_id,
            customer_name="Rayhona",
            customer_username="rayhona",
            items_snapshot=[{"title": "Sharf 🧣", "price": 45000, "qty": 1}],
            total=40000,
            cashback_used=5000,
            status="pending_approval",
            receipt_photo_id="receipt_xyz",
        )
        session.add(order)
        await session.commit()
        order_id = order.id

    mock_callback = MagicMock(spec=CallbackQuery)
    mock_callback.data = f"order_cancel_{order_id}"
    mock_callback.from_user = TgUser(id=admin_id, is_bot=False, first_name="Gulmira")
    mock_callback.answer = AsyncMock()

    mock_message = MagicMock(spec=Message)
    mock_message.photo = [PhotoSize(file_id="receipt_xyz", file_unique_id="u", width=100, height=100)]
    mock_message.caption = f"Buyurtma #{order_id}"
    mock_message.html_text = f"Buyurtma #{order_id}"
    mock_message.edit_caption = AsyncMock()
    mock_callback.message = mock_message

    mock_bot = AsyncMock()
    with patch("bot.handlers.orders.bot", mock_bot), \
         patch("bot.handlers.orders.async_session_factory", async_session):

        await handle_order_cancel(mock_callback)

        async with async_session() as session:
            o = (await session.execute(select(Order).where(Order.id == order_id))).scalars().first()
            assert o.status == "cancelled"

            u = (await session.execute(select(User).where(User.telegram_id == customer_id))).scalars().first()
            # 5000 was used, refunded -> 10000
            assert u.cashback_balance == 10000

        mock_message.edit_caption.assert_called_once()
        assert "BEKOR QILINDI" in mock_message.edit_caption.call_args.kwargs["caption"]
        mock_callback.answer.assert_called_once()


@pytest.mark.asyncio
async def test_receipt_pdf_document_upload_flow(test_db_session):
    """
    Customer uploads a PDF receipt (e.g. from Click or Payme).
    Verifies that PDF documents are recognized, order status becomes pending_approval,
    and admins are alerted with the document.
    """
    async_session = test_db_session
    customer_id = 55667788

    async with async_session() as session:
        session.add(User(telegram_id=customer_id, name="Shahzoda"))
        order = Order(
            user_id=customer_id,
            customer_name="Shahzoda",
            customer_username="shahzoda",
            items_snapshot=[{"title": "Kardigan 🌸", "price": 140000, "qty": 1}],
            total=140000,
            status="awaiting_receipt",
        )
        session.add(order)
        await session.commit()
        order_id = order.id

    mock_message = MagicMock(spec=Message)
    mock_message.from_user = TgUser(id=customer_id, is_bot=False, first_name="Shahzoda")
    mock_message.chat = Chat(id=customer_id, type="private")
    mock_message.photo = None

    mock_doc = Document(
        file_id="pdf_receipt_doc_id_999",
        file_unique_id="doc_u999",
        file_name="click_receipt.pdf",
        mime_type="application/pdf",
        file_size=54321,
    )
    mock_message.document = mock_doc
    mock_message.answer = AsyncMock()

    mock_state = AsyncMock()
    mock_state.get_state.return_value = None

    with patch("bot.handlers.orders.async_session_factory", async_session), \
         patch("bot.services.order_notifier.async_session_factory", async_session), \
         patch("bot.services.order_notifier.bot") as mock_bot:

        # simulate send_photo failing on document file_id, triggering fallback to send_document
        mock_bot.send_photo = AsyncMock(side_effect=Exception("Bad Request: wrong remote file identifier type"))
        mock_bot.send_document = AsyncMock()

        await handle_receipt_upload(mock_message, mock_state)

        # 1. Customer got confirmation
        mock_message.answer.assert_called_once()
        assert "To'lov chekingiz qabul qilindi" in mock_message.answer.call_args.args[0]

        # 2. DB updated
        async with async_session() as session:
            updated_order = (await session.execute(select(Order).where(Order.id == order_id))).scalars().first()
            assert updated_order.status == "pending_approval"
            assert updated_order.receipt_photo_id == "pdf_receipt_doc_id_999"

        # 3. Admins alerted with send_document
        assert mock_bot.send_document.called
        call_kw = mock_bot.send_document.call_args.kwargs
        assert call_kw["document"] == "pdf_receipt_doc_id_999"
        assert f"#{order_id}" in call_kw["caption"]


@pytest.mark.asyncio
async def test_admin_message_edit_with_document(test_db_session):
    """
    Verifies that edit_admin_message safely uses edit_caption when
    the admin message has a document instead of a photo.
    """
    from bot.handlers.orders import edit_admin_message

    mock_callback = MagicMock(spec=CallbackQuery)
    mock_message = MagicMock(spec=Message)
    mock_message.photo = None
    mock_message.document = MagicMock()
    mock_message.caption = "Order #123 caption"
    mock_message.html_text = "Order #123 caption"
    mock_message.edit_caption = AsyncMock()
    mock_message.edit_text = AsyncMock()
    mock_callback.message = mock_message

    await edit_admin_message(mock_callback, "<b>✅ QABUL QILINDI</b>", "Otabek")

    # Must edit caption, NOT crash on edit_text
    mock_message.edit_caption.assert_called_once()
    assert "QABUL QILINDI" in mock_message.edit_caption.call_args.kwargs["caption"]
    mock_message.edit_text.assert_not_called()


@pytest.mark.asyncio
async def test_admin_api_order_status_update_parity(client, test_db_session):
    """
    Tests that updating order status to 'accepted' via Admin REST API
    awards 2% cashback, broadcasts social proof, and notifies customer with contact button.
    """
    async_session = test_db_session
    admin_id = 8643984824
    customer_id = 44556677

    admin_init = generate_test_init_data(user_id=admin_id, first_name="Otabek")

    async with async_session() as session:
        session.add(Admin(telegram_id=admin_id, name="Otabek", role="owner"))
        session.add(User(telegram_id=customer_id, name="Kamila", cashback_balance=500))
        order = Order(
            user_id=customer_id,
            customer_name="Kamila",
            customer_username="kamila_k",
            items_snapshot=[{"title": "Lolita Dress 👗", "price": 200000, "qty": 1}],
            total=200000,
            status="pending_approval",
            receipt_photo_id="receipt_photo_1",
        )
        session.add(order)
        await session.commit()
        order_id = order.id

    mock_bot = AsyncMock()
    with patch("api.routes.admin.bot", mock_bot), \
         patch("bot.services.order_notifier.bot", mock_bot):

        resp = await client.patch(
            f"/api/admin/orders/{order_id}/status",
            json={"status": "accepted"},
            headers={"X-Telegram-Init-Data": admin_init},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "accepted"

        # Check DB cashback awarded: 2% of 200000 is 4000; 500 + 4000 = 4500
        async with async_session() as session:
            u = (await session.execute(select(User).where(User.telegram_id == customer_id))).scalars().first()
            assert u.cashback_balance == 4500

        # Customer notified with contact button
        customer_calls = [
            c for c in mock_bot.send_message.call_args_list
            if c.kwargs.get("chat_id") == customer_id
        ]
        assert len(customer_calls) >= 1
        c_kwargs = customer_calls[0].kwargs
        assert "to'lovingiz tasdiqlandi" in c_kwargs["text"].lower() or "qabul qilindi" in c_kwargs["text"].lower()
        btn = c_kwargs["reply_markup"].inline_keyboard[0][0]
        assert "MOONLIGHT_ADMINNN" in btn.url or "t.me/" in btn.url


@pytest.mark.asyncio
async def test_broadcast_live_order_proof_and_fallback(test_db_session):
    """
    Verifies that broadcast_live_order_proof creates aesthetic proof
    with custom emojis, masks customer data for privacy, and gracefully
    falls back to plain emojis if custom emojis are not supported by the channel.
    """
    order = Order(
        id=77,
        user_id=123456789,
        customer_name="Otabek Kholikov",
        items_snapshot=[
            {"title": "Anime Hoodie", "qty": 2, "size": "XL", "color": "Pushti"},
        ],
        total=250000,
        estimated_cargo=24000,
        status="accepted",
    )

    # 1. Normal run with custom emojis
    mock_bot = AsyncMock()
    await broadcast_live_order_proof(mock_bot, order, target_chat_override=-100999888)

    mock_bot.send_message.assert_called_once()
    call_args = mock_bot.send_message.call_args.kwargs
    assert call_args["chat_id"] == -100999888
    sent_text = call_args["text"]
    assert "Yangi Xarid!" in sent_text
    assert "Anime Hoodie (XL) [Pushti]" in sent_text
    assert "250.000 so'm" in sent_text
    # Privacy masking verification
    assert "Otabek Kholikov" not in sent_text
    assert "123456789" not in sent_text
    from api.services.formatters import mask_customer_name, mask_user_id
    assert mask_customer_name("Otabek Kholikov") in sent_text
    assert mask_user_id(123456789) in sent_text
    # Verified custom emoji tags present
    assert "<tg-emoji" in sent_text

    # 2. Fallback run when channel forbids custom emojis
    mock_bot_fallback = AsyncMock()
    mock_bot_fallback.send_message.side_effect = [
        RuntimeError("Bad Request: can't use custom emoji"),
        AsyncMock(),
    ]
    await broadcast_live_order_proof(mock_bot_fallback, order, target_chat_override=-100999888)
    assert mock_bot_fallback.send_message.call_count == 2
    fallback_text = mock_bot_fallback.send_message.call_args_list[1].kwargs["text"]
    assert "<tg-emoji" not in fallback_text
    assert "Yangi Xarid!" in fallback_text


@pytest.mark.asyncio
async def test_customer_receipt_media_group_deduplication(test_db_session):
    """
    Verifies that when a customer uploads multiple photos as an album (media group),
    only 1 confirmation is sent to the customer and admins are alerted only once.
    """
    from bot.handlers.orders import handle_receipt_upload
    from aiogram.fsm.context import FSMContext

    customer_id = 88776655
    async with test_db_session() as session:
        session.add(
            Order(
                user_id=customer_id,
                customer_name="Kamola",
                items_snapshot=[{"product_id": 1, "title": "Kofta", "price": 90000, "qty": 1}],
                total=90000,
                status="awaiting_receipt",
            )
        )
        await session.commit()

    mock_state = AsyncMock(spec=FSMContext)
    mock_state.get_state.return_value = None

    msg1 = MagicMock()
    msg1.from_user = MagicMock()
    msg1.from_user.id = customer_id
    msg1.media_group_id = "album_receipt_999"
    msg1.photo = [MagicMock(file_id="receipt_photo_part1")]
    msg1.document = None
    msg1.answer = AsyncMock()

    msg2 = MagicMock()
    msg2.from_user = MagicMock()
    msg2.from_user.id = customer_id
    msg2.media_group_id = "album_receipt_999"
    msg2.photo = [MagicMock(file_id="receipt_photo_part2")]
    msg2.document = None
    msg2.answer = AsyncMock()

    with patch("bot.handlers.orders.async_session_factory", test_db_session), \
         patch("bot.services.order_notifier.async_session_factory", test_db_session), \
         patch("bot.services.order_notifier.notify_admins_new_receipt", AsyncMock()) as mock_notify:
        # First part of album
        await handle_receipt_upload(msg1, mock_state)
        # Second part of album
        await handle_receipt_upload(msg2, mock_state)

        # Customer answer was called only once for part 1 (part 2 deduplicated)
        assert msg1.answer.call_count == 1
        assert msg2.answer.call_count == 0
        # Admin notified only once
        assert mock_notify.call_count == 1


@pytest.mark.asyncio
async def test_customer_receipt_passes_through_admin_router_e2e(test_db_session):
    """
    End-to-end integration test verifying that in an aiogram Dispatcher containing
    both admin.router and orders.router, a customer payment receipt photo is NOT
    intercepted by admin.router and is dispatched to orders.handle_receipt_upload,
    successfully transitioning the order status from awaiting_receipt to pending_approval.
    """
    from aiogram import Dispatcher
    from aiogram.fsm.storage.memory import MemoryStorage
    from aiogram.types import Update
    from bot.handlers.admin import router as admin_router
    from bot.handlers.orders import router as orders_router

    customer_id = 44556677
    async with test_db_session() as session:
        session.add(
            Order(
                user_id=customer_id,
                customer_name="Zilola",
                items_snapshot=[{"product_id": 1, "title": "Kofta", "price": 90000, "qty": 1}],
                total=90000,
                status="awaiting_receipt",
            )
        )
        await session.commit()

    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(admin_router)
    dp.include_router(orders_router)

    user = TgUser(id=customer_id, is_bot=False, first_name="Zilola")
    chat = Chat(id=customer_id, type="private")
    photo = [PhotoSize(file_id="receipt_photo_e2e", file_unique_id="u_e2e", width=200, height=200)]

    msg = Message(
        message_id=50,
        date=1700000000,
        chat=chat,
        from_user=user,
        photo=photo,
    )
    update = Update(update_id=1001, message=msg)

    mock_bot = AsyncMock()
    mock_bot.id = 12345
    mock_bot.send_message = AsyncMock()

    with patch("bot.handlers.admin.async_session_factory", test_db_session), \
         patch("bot.handlers.admin.is_user_admin", AsyncMock(return_value=False)), \
         patch("bot.handlers.orders.async_session_factory", test_db_session), \
         patch("bot.services.order_notifier.async_session_factory", test_db_session), \
         patch("bot.services.order_notifier.notify_admins_new_receipt", AsyncMock()):
        await dp.feed_update(mock_bot, update)

    async with test_db_session() as session:
        res = await session.execute(select(Order).where(Order.user_id == customer_id))
        order = res.scalars().first()
        assert order is not None
        assert order.status == "pending_approval"
        assert order.receipt_photo_id == "receipt_photo_e2e"



