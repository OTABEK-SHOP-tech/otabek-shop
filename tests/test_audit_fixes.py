import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from aiogram.types import Message, CallbackQuery, PhotoSize
from sqlalchemy import select

from bot.handlers.admin import (
    handle_importable_post,
    _media_group_buffer,
    _processed_media_groups,
    _user_active_batch,
)
from bot.handlers.start import (
    send_product_deep_link,
    handle_subscription_confirm,
)
from bot.services.subscription import (
    is_user_admin,
    check_single_membership,
    get_subscription_markup,
)
from db.models import Product, Admin, Setting


@pytest.mark.asyncio
async def test_admin_two_clean_photos_not_dropped(test_db_session):
    """
    Item 1: Verify that 2 clean photos are BOTH preserved and not artificially truncated
    even if source_price is present and OCR checked the last photo.
    """
    from bot.handlers.admin import process_product_import, ProductWizard

    fake_message = MagicMock(spec=Message)
    fake_message.from_user = MagicMock(id=8643984824, full_name="Admin")
    fake_message.answer = AsyncMock()

    fake_state = AsyncMock()
    fake_state.get_data = AsyncMock(return_value={})
    fake_state.update_data = AsyncMock()
    fake_state.set_state = AsyncMock()

    # Pass 2 clean photo byte buffers so OCR is genuinely executed
    photos = [b"clean_model_photo_1_bytes", b"clean_model_photo_2_bytes"]
    raw_text = "Chiroyli ko'ylak 150000 som"

    with patch("bot.handlers.admin.extract_product_from_image", new_callable=AsyncMock) as mock_vision, \
         patch("bot.handlers.admin.is_phone_screenshot", return_value=False), \
         patch("bot.handlers.admin.async_session_factory", test_db_session):

        mock_vision.return_value = {
            "success": True,
            "source_price": 50.0,
            "title": "Chiroyli ko'ylak",
            "category": "kiyim",
            "is_spec_screenshot": False,
        }

        await process_product_import(
            message=fake_message,
            state=fake_state,
            raw_text=raw_text,
            photos=photos,
            source_label="Sehrli import",
        )

        assert mock_vision.called
        assert fake_state.update_data.called
        update_args = fake_state.update_data.call_args[1]
        assert len(update_args["photos"]) == 2
        assert update_args["photos"] == [b"clean_model_photo_1_bytes", b"clean_model_photo_2_bytes"]


@pytest.mark.asyncio
async def test_admin_spec_screenshot_is_excluded(test_db_session):
    """
    Item 1: Verify that an actual spec screenshot (is_spec_screenshot=True)
    IS excluded, leaving only clean model photos.
    """
    from bot.handlers.admin import process_product_import

    fake_message = MagicMock(spec=Message)
    fake_message.from_user = MagicMock(id=8643984824, full_name="Admin")
    fake_message.answer = AsyncMock()

    fake_state = AsyncMock()
    fake_state.get_data = AsyncMock(return_value={})
    fake_state.update_data = AsyncMock()
    fake_state.set_state = AsyncMock()

    photos = [b"clean_model_photo_bytes", b"spec_screenshot_bytes"]
    raw_text = "Chiroyli ko'ylak 150000 som"

    async def mock_extract(img_bytes):
        if img_bytes == b"spec_screenshot_bytes":
            return {
                "success": True,
                "source_price": 45.0,
                "title": "Koylak",
                "category": "kiyim",
                "is_spec_screenshot": True,
            }
        return {"success": False}

    with patch("bot.handlers.admin.extract_product_from_image", side_effect=mock_extract) as mock_vision, \
         patch("bot.handlers.admin.is_phone_screenshot", return_value=False), \
         patch("bot.handlers.admin.async_session_factory", test_db_session):

        await process_product_import(
            message=fake_message,
            state=fake_state,
            raw_text=raw_text,
            photos=photos,
            source_label="Sehrli import",
        )

        assert fake_state.update_data.called
        update_args = fake_state.update_data.call_args[1]
        # Only the clean model photo should be retained
        assert len(update_args["photos"]) == 1
        assert update_args["photos"] == [b"clean_model_photo_bytes"]


@pytest.mark.asyncio
async def test_admin_single_photo_no_10s_blacklist_drop():
    """
    Item 2: Verify that separate (non-album) photos do not get blacklisted for 10s,
    so a subsequent product sent a moment later is NOT silently dropped.
    """
    user_id = 99887766
    _processed_media_groups.clear()
    _media_group_buffer.clear()
    _user_active_batch.clear()

    msg1 = MagicMock(spec=Message)
    msg1.from_user = MagicMock(id=user_id)
    msg1.photo = [MagicMock(spec=PhotoSize, file_id="file_photo_1")]
    msg1.document = None
    msg1.media_group_id = None
    msg1.caption = "First product 50000"
    msg1.text = None
    msg1.answer = AsyncMock()

    with patch("bot.handlers.admin.process_product_import", new_callable=AsyncMock) as mock_import:
        # Simulate handling message 1
        await handle_importable_post(msg1, state=AsyncMock())
        assert mock_import.call_count == 1
        # The dynamic key or single photos should NOT be stored in _processed_media_groups
        for k in _processed_media_groups:
            assert not k.startswith(f"user_{user_id}")

        # Now send second message immediately (within 1 second)
        msg2 = MagicMock(spec=Message)
        msg2.from_user = MagicMock(id=user_id)
        msg2.photo = [MagicMock(spec=PhotoSize, file_id="file_photo_2")]
        msg2.document = None
        msg2.media_group_id = None
        msg2.caption = "Second product 60000"
        msg2.text = None
        msg2.answer = AsyncMock()

        await handle_importable_post(msg2, state=AsyncMock())
        # Second product should be processed, NOT silently dropped!
        assert mock_import.call_count == 2


@pytest.mark.asyncio
async def test_admin_photo_buffer_synchronous_registration():
    """
    Item 2: Buffer entry is written synchronously before answer network await,
    preventing concurrent photos in the same batch from overwriting each other.
    """
    user_id = 11223344
    _media_group_buffer.clear()
    _user_active_batch.clear()

    # Pre-populate active batch
    batch_key = f"user_{user_id}_testbatch"
    _user_active_batch[user_id] = batch_key
    _media_group_buffer[batch_key] = {
        "photos": ["photo_1"],
        "text": "Initial text",
        "message": MagicMock(),
        "status_msg": None,
        "last_active": time.time(),
    }

    # Subsequent photo arrives
    msg2 = MagicMock(spec=Message)
    msg2.from_user = MagicMock(id=user_id)
    msg2.photo = [MagicMock(spec=PhotoSize, file_id="photo_2")]
    msg2.document = None
    msg2.media_group_id = None
    msg2.caption = None
    msg2.text = None

    await handle_importable_post(msg2, state=AsyncMock())

    # Verify photo_2 was appended to active buffer
    assert "photo_2" in _media_group_buffer[batch_key]["photos"]
    assert len(_media_group_buffer[batch_key]["photos"]) == 2

    # Cleanup
    _media_group_buffer.clear()
    _user_active_batch.clear()


@pytest.mark.asyncio
async def test_admin_debounce_cancellation_releases_buffer():
    """
    Item 2: If message.answer is cancelled (e.g. task cancellation),
    the buffer and user active batch are cleanly popped by finally, preventing deadlock.
    """
    user_id = 445566
    _media_group_buffer.clear()
    _user_active_batch.clear()

    msg = MagicMock(spec=Message)
    msg.from_user = MagicMock(id=user_id)
    msg.photo = [MagicMock(spec=PhotoSize, file_id="photo_cancel")]
    msg.document = None
    msg.media_group_id = None
    msg.caption = None
    msg.text = None
    # Simulate asyncio.CancelledError during message.answer
    msg.answer = AsyncMock(side_effect=asyncio.CancelledError())

    with pytest.raises(asyncio.CancelledError):
        await handle_importable_post(msg, state=AsyncMock())

    # Buffer and active batch must be empty despite the cancellation!
    assert len(_media_group_buffer) == 0
    assert user_id not in _user_active_batch


@pytest.mark.asyncio
async def test_admin_debounce_accumulates_captions():
    """
    Item 2: Consecutive photos in the active batch accumulate distinct captions.
    """
    user_id = 778899
    _media_group_buffer.clear()
    _user_active_batch.clear()

    batch_key = f"user_{user_id}_testaccum"
    _user_active_batch[user_id] = batch_key
    _media_group_buffer[batch_key] = {
        "photos": ["photo_1"],
        "text": "Qizil ko'ylak",
        "message": MagicMock(),
        "status_msg": None,
        "last_active": time.time(),
    }

    msg2 = MagicMock(spec=Message)
    msg2.from_user = MagicMock(id=user_id)
    msg2.photo = [MagicMock(spec=PhotoSize, file_id="photo_2")]
    msg2.document = None
    msg2.media_group_id = None
    msg2.caption = "Razmer L, 120000 som"
    msg2.text = None

    await handle_importable_post(msg2, state=AsyncMock())

    # Both captions should be concatenated
    assert "Qizil ko'ylak" in _media_group_buffer[batch_key]["text"]
    assert "Razmer L, 120000 som" in _media_group_buffer[batch_key]["text"]

    _media_group_buffer.clear()
    _user_active_batch.clear()


@pytest.mark.asyncio
async def test_deep_link_product_post_subscription_routing(test_db_session):
    """
    Item 3: When a customer subscribes after /start product_<id>,
    handle_subscription_confirm sends the product card instead of falling back to general greeting.
    """
    async with test_db_session() as session:
        prod = Product(
            id=777,
            title="Kuzgi Jempir 🌸",
            price=120000,
            category="jempir",
            photos=["jempir1.jpg"],
            weight_grams=300,
            in_stock=True,
        )
        session.add(prod)
        await session.commit()

    callback = MagicMock(spec=CallbackQuery)
    callback.from_user = MagicMock(id=554433, full_name="Xaridor")
    callback.data = "check_sub:product_777"
    callback.message = MagicMock(spec=Message)
    callback.message.answer = AsyncMock()
    callback.message.answer_photo = AsyncMock()
    callback.message.delete = AsyncMock()
    callback.answer = AsyncMock()

    with patch("bot.handlers.start.async_session_factory", test_db_session), \
         patch("bot.handlers.start.check_dual_subscription", new_callable=AsyncMock) as mock_dual, \
         patch("bot.handlers.start.send_welcome_greeting", new_callable=AsyncMock) as mock_welcome, \
         patch("bot.handlers.start.send_product_deep_link", new_callable=AsyncMock) as mock_send_prod:

        mock_dual.return_value = (True, True, "https://t.me/channel", "https://t.me/chat")
        mock_send_prod.return_value = True

        await handle_subscription_confirm(callback)

        # Confirm subscription was accepted
        callback.answer.assert_called_with("✅ Rahmat! Obuna muvaffaqiyatli tasdiqlandi!", show_alert=False)
        # Deep link product sent directly
        mock_send_prod.assert_called_once_with(callback.message, 777)
        # General greeting was bypassed
        mock_welcome.assert_not_called()


@pytest.mark.asyncio
async def test_deep_link_contest_post_subscription_routing(test_db_session):
    """
    Item 3: When a user clicks 'Tasdiqlash' with contest context,
    routes to contest dashboard.
    """
    callback = MagicMock(spec=CallbackQuery)
    callback.from_user = MagicMock(id=554433, full_name="Xaridor")
    callback.data = "check_sub:konkurs"
    callback.message = MagicMock(spec=Message)
    callback.message.answer = AsyncMock()
    callback.message.delete = AsyncMock()
    callback.answer = AsyncMock()

    with patch("bot.handlers.start.async_session_factory", test_db_session), \
         patch("bot.handlers.start.check_dual_subscription", new_callable=AsyncMock) as mock_dual, \
         patch("bot.handlers.start.send_welcome_greeting", new_callable=AsyncMock) as mock_welcome, \
         patch("bot.handlers.contest.show_user_contest_dashboard", new_callable=AsyncMock) as mock_contest:

        mock_dual.return_value = (True, True, "https://t.me/channel", "https://t.me/chat")

        await handle_subscription_confirm(callback)

        mock_contest.assert_called_once_with(callback.message, 554433)
        mock_welcome.assert_not_called()


@pytest.mark.asyncio
async def test_cloud_sync_does_not_skip_distinct_products_with_same_title():
    """
    Item 4: Two products with same title but different photos must NOT be skipped as duplicates.
    """
    from api.services.cloud_sync import sync_product_to_cloud

    product_to_sync = MagicMock(spec=Product)
    product_to_sync.id = 101
    product_to_sync.title = "Jempir 🌸"
    product_to_sync.description = "Qora jempir"
    product_to_sync.price = 150000
    product_to_sync.old_price = None
    product_to_sync.source_price = 45.0
    product_to_sync.category = "jempir"
    product_to_sync.photos = ["photo_black.jpg"]
    product_to_sync.sizes = ["S", "M"]
    product_to_sync.colors = ["Qora"]
    product_to_sync.weight_grams = 350
    product_to_sync.in_stock = True
    product_to_sync.is_new = True
    product_to_sync.is_hit = False

    # Existing cloud items contain a different Jempir (white, different photo and different ID)
    cloud_existing = [
        {
            "id": 99,
            "title": "Jempir 🌸",
            "photos": ["photo_white.jpg"],
            "price": 120000,
            "source_price": 35.0,
        }
    ]

    mock_client = AsyncMock()
    # categories check
    mock_client.get.side_effect = [
        MagicMock(is_success=True, json=lambda: [{"slug": "jempir"}]),
        MagicMock(is_success=True, json=lambda: cloud_existing),
    ]
    mock_client.post.return_value = MagicMock(is_success=True, status_code=201)

    with patch("api.services.cloud_sync.settings") as mock_settings, \
         patch("api.services.cloud_sync.generate_admin_init_data", return_value="fake_init_data"), \
         patch("httpx.AsyncClient") as mock_httpx:
        mock_settings.WEBAPP_URL = "https://test-cloud.onrender.com"
        mock_settings.ADMIN_KEY = "test_key"
        mock_httpx.return_value.__aenter__.return_value = mock_client

        res = await sync_product_to_cloud(product_to_sync)
        # Should NOT say already exists and skip post; it should call post to create product!
        assert res is True
        assert mock_client.post.called


@pytest.mark.asyncio
async def test_cloud_sync_skips_when_title_and_photo_match():
    """
    Item 4: Same product with identical title and overlapping photos is correctly identified as existing.
    """
    from api.services.cloud_sync import sync_product_to_cloud

    product_to_sync = MagicMock(spec=Product)
    product_to_sync.id = 101
    product_to_sync.title = "Jempir 🌸"
    product_to_sync.category = "jempir"
    product_to_sync.photos = ["photo_black.jpg"]
    product_to_sync.price = 150000
    product_to_sync.source_price = 45.0

    cloud_existing = [
        {
            "id": 101,
            "title": "Jempir 🌸",
            "photos": ["photo_black.jpg"],
            "price": 150000,
        }
    ]

    mock_client = AsyncMock()
    mock_client.get.side_effect = [
        MagicMock(is_success=True, json=lambda: [{"slug": "jempir"}]),
        MagicMock(is_success=True, json=lambda: cloud_existing),
    ]

    with patch("api.services.cloud_sync.settings") as mock_settings, \
         patch("api.services.cloud_sync.generate_admin_init_data", return_value="fake_init_data"), \
         patch("httpx.AsyncClient") as mock_httpx:
        mock_settings.WEBAPP_URL = "https://test-cloud.onrender.com"
        mock_settings.ADMIN_KEY = "test_key"
        mock_httpx.return_value.__aenter__.return_value = mock_client

        res = await sync_product_to_cloud(product_to_sync)
        # Already exists -> returns True without calling client.post
        assert res is True
        assert not mock_client.post.called


@pytest.mark.asyncio
async def test_cloud_sync_different_photos_same_id_not_skipped():
    """
    Item 4: Two products with same title and coincidental identical ID but different photos
    MUST NOT be skipped as duplicates.
    """
    from api.services.cloud_sync import sync_product_to_cloud

    product_to_sync = MagicMock(spec=Product)
    product_to_sync.id = 55
    product_to_sync.title = "Jempir 🌸"
    product_to_sync.category = "jempir"
    product_to_sync.photos = ["photo_new_red.jpg"]
    product_to_sync.price = 150000
    product_to_sync.old_price = None
    product_to_sync.source_price = 45.0
    product_to_sync.sizes = ["M"]
    product_to_sync.colors = ["Qizil"]
    product_to_sync.weight_grams = 300
    product_to_sync.in_stock = True
    product_to_sync.is_new = True
    product_to_sync.is_hit = False

    # Cloud product has id 55 and same title, but DIFFERENT photos!
    cloud_existing = [
        {
            "id": 55,
            "title": "Jempir 🌸",
            "photos": ["photo_old_blue.jpg"],
            "price": 120000,
        }
    ]

    mock_client = AsyncMock()
    mock_client.get.side_effect = [
        MagicMock(is_success=True, json=lambda: [{"slug": "jempir"}]),
        MagicMock(is_success=True, json=lambda: cloud_existing),
    ]
    mock_client.post.return_value = MagicMock(is_success=True, status_code=201)

    with patch("api.services.cloud_sync.settings") as mock_settings, \
         patch("api.services.cloud_sync.generate_admin_init_data", return_value="fake_init_data"), \
         patch("httpx.AsyncClient") as mock_httpx:
        mock_settings.WEBAPP_URL = "https://test-cloud.onrender.com"
        mock_settings.ADMIN_KEY = "test_key"
        mock_httpx.return_value.__aenter__.return_value = mock_client

        res = await sync_product_to_cloud(product_to_sync)
        # Different photos mean distinct product: MUST be posted to cloud!
        assert res is True
        assert mock_client.post.called


@pytest.mark.asyncio
async def test_api_products_admin_vs_public_pricing(test_db_session):
    """
    Item 4: /api/products returns source_price when admin token is present,
    and strips it for regular public callers.
    """
    from api.routes.products import list_products, get_product_detail
    from api.auth import TelegramUser

    async with test_db_session() as session:
        prod = Product(
            id=888,
            title="Maxsus Sviter 🌸",
            price=200000,
            source_price=75000,
            category="jempir",
            photos=["sviter.jpg"],
            in_stock=True,
        )
        session.add(prod)
        await session.commit()

        # 1. Public caller (no admin)
        public_list = await list_products(db=session, user=None)
        p_item = next((p for p in public_list if p.id == 888), None)
        assert p_item is not None
        assert p_item.source_price is None

        # 2. Admin caller
        admin_user = TelegramUser(id=8643984824, first_name="Admin", is_admin=True)
        admin_list = await list_products(db=session, user=admin_user)
        admin_item = next((p for p in admin_list if p.id == 888), None)
        assert admin_item is not None
        assert admin_item.source_price == 75000
