import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from sqlalchemy import select

from api.services.formatters import (
    parse_sizes,
    format_sizes_display,
    calculate_margin_percent,
    calculate_retail_price,
    parse_channel_post,
    build_channel_caption,
    format_price,
)
from api.services.telegram_fetcher import (
    extract_telegram_post_links,
    fetch_telegram_post_embed,
)
from bot.services.channel_post import post_product_to_channel
from bot.services.premium_emojis import upgrade_to_premium_emojis
from db.models import Category, Product, Setting, Admin


def test_parse_sizes_various_formats():
    # Range notation S-2XL
    assert parse_sizes("S-2XL") == ["S", "M", "L", "XL", "2XL"]
    assert parse_sizes("S - 2XL") == ["S", "M", "L", "XL", "2XL"]
    assert parse_sizes("Razmer: S-2XL") == ["S", "M", "L", "XL", "2XL"]
    assert parse_sizes("👗 Razmer: S-XXL") == ["S", "M", "L", "XL", "2XL"]
    assert parse_sizes("M-3XL") == ["M", "L", "XL", "2XL", "3XL"]

    # Numeric shoe range
    assert parse_sizes("36-40") == ["36", "37", "38", "39", "40"]
    assert parse_sizes("Razmer: 35-38") == ["35", "36", "37", "38"]

    # Comma or slash separated
    assert parse_sizes("S, M, L, XL") == ["S", "M", "L", "XL"]
    assert parse_sizes("S/M/L") == ["S", "M", "L"]

    # Keyword sizes
    assert parse_sizes("standart") == ["Standart"]
    assert parse_sizes("Free size") == ["Free size"]

    # Empty
    assert parse_sizes("") == []


def test_format_sizes_display():
    assert format_sizes_display(["S", "M", "L", "XL", "2XL"]) == "S-2XL"
    assert format_sizes_display(["36", "37", "38", "39", "40"]) == "36-40"
    assert format_sizes_display(["S", "XL"]) == "S, XL"
    assert format_sizes_display([]) == ""


def test_profit_margin_calculation_25_to_35_percent():
    # 95.000 so'm source price -> 30% margin -> 123.500 -> 124.000 so'm
    source_price = 95000
    margin = calculate_margin_percent(source_price)
    assert 25.0 <= margin <= 35.0
    retail = calculate_retail_price(source_price)
    assert retail == 124000

    # Cheap items (< 80.000 so'm) get 35% margin
    cheap_source = 40000
    assert calculate_margin_percent(cheap_source) == 35.0
    assert calculate_retail_price(cheap_source) == 54000  # 40000 * 1.35 = 54000

    # Expensive items (> 200.000 so'm) get 25% margin
    exp_source = 300000
    assert calculate_margin_percent(exp_source) == 25.0
    assert calculate_retail_price(exp_source) == 375000  # 300000 * 1.25 = 375000

    # Custom clamped margin
    assert calculate_retail_price(100000, margin_percent=10.0) == 125000  # Clamped to min 25%
    assert calculate_retail_price(100000, margin_percent=50.0) == 135000  # Clamped to max 35%


def test_parse_competitor_post_sakura_style():
    sample_post = (
        "#hoodie 🌸\n"
        "✨ Pushti Vintage Hoodie\n"
        "💰 Narx: 95.000 so'm\n"
        "👗 Razmer: S-2XL\n"
        "📦 Kargo: 12.000 so'm / 100g\n"
        "⏳ Yetkazib berish: 10-15 kun\n"
        "🌸 Otzivlar: @sakura_shop_otzv\n"
        "💌 Admin: @sakura_admin"
    )

    parsed = parse_channel_post(sample_post, apply_margin=True)
    assert parsed["category"] == "hoodie"
    assert "Pushti Vintage Hoodie" in parsed["title"]
    assert parsed["source_price"] == 95000
    assert parsed["price"] == 124000  # Retail price with 30% margin
    assert parsed["sizes"] == ["S", "M", "L", "XL", "2XL"]
    assert parsed["cargo_rate"] == 12000


def test_extract_telegram_post_links():
    text1 = "Mana post havolasi: https://t.me/sakura_shop_uz/5512 tekshirib ko'ring"
    links1 = extract_telegram_post_links(text1)
    assert len(links1) == 1
    assert links1[0]["chat_ref"] == "sakura_shop_uz"
    assert links1[0]["message_id"] == 5512
    assert not links1[0]["is_private"]

    # Web format with /s/
    text_web = "Web link: https://t.me/s/sakura_shop_uz/5512"
    links_web = extract_telegram_post_links(text_web)
    assert len(links_web) == 1
    assert links_web[0]["chat_ref"] == "sakura_shop_uz"
    assert links_web[0]["message_id"] == 5512

    # @channel/123 format
    text_at = "At format: @sakura_shop_uz/5512"
    links_at = extract_telegram_post_links(text_at)
    assert len(links_at) == 1
    assert links_at[0]["chat_ref"] == "sakura_shop_uz"
    assert links_at[0]["message_id"] == 5512

    text2 = "Yopiq kanal: https://t.me/c/1234567890/42"
    links2 = extract_telegram_post_links(text2)
    assert len(links2) == 1
    assert links2[0]["is_private"]
    assert links2[0]["chat_ref"] == "1234567890"
    assert links2[0]["message_id"] == 42


def test_parse_sizes_natural_language_edge_cases():
    # Conversational text attached to sizes
    assert parse_sizes("Razmer: S-2XL mavjud 🌸") == ["S", "M", "L", "XL", "2XL"]
    assert parse_sizes("Razmer: S-2XL (oversize)") == ["S", "M", "L", "XL", "2XL"]
    assert parse_sizes("Razmer: 36 dan 40 gacha") == ["36", "37", "38", "39", "40"]
    assert parse_sizes("36-40 gacha") == ["36", "37", "38", "39", "40"]
    assert parse_sizes("S dan 2XL gacha") == ["S", "M", "L", "XL", "2XL"]
    assert parse_sizes("👗 S-XXL") == ["S", "M", "L", "XL", "2XL"]


def test_parse_post_with_cyrillic_tag_and_dress_emoji_only():
    post = (
        "#худи 🌸\n"
        "Oversize Pushti Hudi\n"
        "💰 95 000 som\n"
        "👗 S-XXL\n"
        "📦 12.000 / 100g\n"
    )
    parsed = parse_channel_post(post, apply_margin=True)
    assert parsed["category"] == "hoodie"
    assert parsed["source_price"] == 95000
    assert parsed["price"] == 124000
    assert parsed["sizes"] == ["S", "M", "L", "XL", "2XL"]
    assert parsed["cargo_rate"] == 12000


def test_parse_post_with_k_and_ming_prices():
    post1 = "#hoodie 🌸\nNarxi: 95k\nRazmer: S-2XL"
    parsed1 = parse_channel_post(post1, apply_margin=True)
    assert parsed1["source_price"] == 95000
    assert parsed1["price"] == 124000

    post2 = "#jempir 🌸\nNarxi: 120 ming so'm\nRazmer: Standart"
    parsed2 = parse_channel_post(post2, apply_margin=True)
    assert parsed2["source_price"] == 120000
    assert parsed2["price"] == 156000  # 120000 + 30% = 156000


def test_parse_post_with_eski_narx_discount():
    post = (
        "#hoodie 🌸\n"
        "✨ Pushti Vintage Hoodie\n"
        "Eski narx: 130.000 so'm\n"
        "Narxi: 95.000 so'm\n"
        "👗 Razmer: S-2XL\n"
    )
    parsed = parse_channel_post(post, apply_margin=True)
    assert parsed["source_price"] == 95000  # Active price, not old price
    assert parsed["old_price"] == 130000
    assert parsed["price"] == 124000


@pytest.mark.asyncio
async def test_channel_post_fallback_on_premium_rejection(test_db_session):
    async with test_db_session() as session:
        # Check if category exists
        res_cat = await session.execute(select(Category).where(Category.slug == "test_cat"))
        if not res_cat.scalars().first():
            cat = Category(slug="test_cat", name="Test", emoji="🌸", sort_order=1)
            session.add(cat)

        prod = Product(
            id=9999,
            title="Test Item",
            price=124000,
            source_price=95000,
            category="test_cat",
            photos=["test.jpg"],
            sizes=["S", "M"],
        )
        session.add(prod)

        res_ch = await session.execute(select(Setting).where(Setting.key == "channel_id"))
        ch_setting = res_ch.scalars().first()
        if ch_setting:
            ch_setting.value = "-1001234567890"
        else:
            session.add(Setting(key="channel_id", value="-1001234567890"))
        await session.commit()

    call_count = 0

    async def fake_send_photo(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            # First attempt with premium custom emojis fails (e.g. channel doesn't allow custom emoji)
            raise RuntimeError("Bad Request: can't use custom emoji")
        # Second attempt with standard fallback emojis succeeds
        msg = MagicMock()
        msg.message_id = 777
        return msg

    with patch("bot.services.channel_post.async_session_factory", test_db_session):
        with patch("bot.services.channel_post.bot") as mock_bot:
            mock_bot.get_me = AsyncMock(return_value=MagicMock(username="moonlight_bot"))
            mock_bot.send_photo = AsyncMock(side_effect=fake_send_photo)

            res = await post_product_to_channel(prod)
            assert res["success"] is True
            assert res["channel_message_id"] == 777
            assert call_count == 2  # Proves it retried and succeeded via fallback!


@pytest.mark.asyncio
async def test_fetch_telegram_post_embed_mock():
    fake_html = """
    <html>
      <div class="tgme_widget_message_text">
        #wig 🌸<br>
        Anime Cosplay Parik Pushti<br>
        💰 Narxi: 110.000 so'm<br>
        👗 Razmer: Standart<br>
        📦 Kargo: 12.000 so'm / 100g<br>
      </div>
      <div class="tgme_widget_message_photo_wrap" style="background-image:url('https://cdn4.telesco.pe/file/photo1.jpg')"></div>
    </html>
    """

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = fake_html

    with patch("httpx.AsyncClient.get", return_value=mock_resp):
        with patch("api.services.telegram_fetcher.download_image_to_cache", return_value="import_photo.jpg"):
            res = await fetch_telegram_post_embed("sakura_shop_uz", 123)
            assert res["success"]
            assert "#wig" in res["raw_text"]
            assert "110.000" in res["raw_text"]
            assert len(res["photos"]) == 1


def test_build_channel_caption_adapted_moonlight_style():
    caption = build_channel_caption(
        category_slug="hoodie",
        price=124000,
        cargo_rate=12000,
        delivery_days="10–15 kun ichida",
        contact_username="MOONLIGHT_ADMINNN",
        title="Pushti Vintage Hoodie",
        sizes=["S", "M", "L", "XL", "2XL"],
        reviews_channel="moonlight_shop_otzv",
        cargo_separate=True,
        adapted_style=True,
    )

    assert "#hoodie 🌸" in caption
    assert "Pushti Vintage Hoodie" in caption
    assert "🎟️ Narx: 124.000 so'm" in caption
    assert "🐾 Razmer: S-2XL" in caption
    assert "🌸 Kargo: 12.000 so'm / 100g (alohida)" in caption
    assert "⏳ Yetkazib berish: 10–15 kun ichida" in caption
    assert "✔️ Otzivlar: @moonlight_shop_otzv" in caption
    assert "@MOONLIGHT_ADMINNN" in caption

    # Check Telegram premium upgrade
    upgraded = upgrade_to_premium_emojis(caption)
    assert '<tg-emoji' in upgraded
    assert '5377599075237502153' in upgraded  # TG_TICKET custom emoji (🎟️)


def test_parse_chinese_yuan_prices():
    from api.services.formatters import parse_channel_post

    # 35 yuan
    post1 = "#hoodie 🌸\nNarxi: 35 yuan\nRazmer: S-2XL"
    parsed1 = parse_channel_post(post1, apply_margin=True)
    # 35 * 1800 = 63000 UZS source (<80k -> 35% margin) -> 63000 * 1.35 = 85050 -> 85000 UZS retail
    assert parsed1["source_price"] == 63000
    assert parsed1["price"] == 85000

    # ¥50
    post2 = "#jempir 🌸\nNarxi: ¥50\nRazmer: Standart"
    parsed2 = parse_channel_post(post2, apply_margin=True)
    # 50 * 1800 = 90000 UZS source, +30% = 117000 UZS retail
    assert parsed2["source_price"] == 90000
    assert parsed2["price"] == 117000


def test_is_importable_message_chinese_marketplace():
    from bot.handlers.admin import is_importable_message
    from unittest.mock import MagicMock

    msg = MagicMock()
    msg.caption = None
    msg.text = "https://mobile.yangkeduo.com/goods.html?ps=L9V9tKhosS\nYang keduo"
    msg.forward_origin = None
    msg.forward_from_chat = None
    msg.forward_date = None

    assert is_importable_message(msg) is True


@pytest.mark.asyncio
async def test_auto_create_category_and_channel_post(test_db_session):
    async with test_db_session() as session:
        # Category "hoodie" doesn't exist initially
        res_cat = await session.execute(select(Category).where(Category.slug == "hoodie"))
        assert res_cat.scalars().first() is None

        # Create category on the fly as done during product ingestion
        cat = Category(slug="hoodie", name="Hoodie", emoji="🧥", sort_order=10)
        session.add(cat)
        await session.commit()

        # Create product with source_price and retail price
        prod = Product(
            title="Vintage Oversize Hoodie",
            price=124000,
            source_price=95000,
            category="hoodie",
            photos=["hoodie1.jpg"],
            sizes=["S", "M", "L", "XL", "2XL"],
        )
        session.add(prod)
        await session.commit()
        await session.refresh(prod)

        assert prod.id is not None
        assert prod.source_price == 95000
        assert prod.price == 124000
        assert prod.sizes == ["S", "M", "L", "XL", "2XL"]


def test_calculate_cargo_rate_with_profit_formula():
    from api.services.formatters import calculate_cargo_rate_with_profit

    # AVTO: base $5.88 / kg -> $0.588 / 100g -> 7585 uzs + 2000 profit = 9585 -> 10.000 so'm / 100g
    avto_rate = calculate_cargo_rate_with_profit(5.88, profit_uzs_per_100g=2000, usd_rate=12900)
    assert avto_rate == 10000

    # AVIA: base $8.99 / kg -> $0.899 / 100g -> 11597 uzs + 2000 profit = 13597 -> 14.000 so'm / 100g
    avia_rate = calculate_cargo_rate_with_profit(8.99, profit_uzs_per_100g=2000, usd_rate=12900)
    assert avia_rate == 14000


def test_build_channel_caption_dual_tariffs_avia_and_avto():
    caption = build_channel_caption(
        category_slug="hoodie",
        price=124000,
        cargo_rate_avia=14000,
        cargo_rate_avto=10000,
        delivery_days_avia="7–9 kun",
        delivery_days_avto="14–18 kun",
        contact_username="MOONLIGHT_ADMINNN",
        title="Pushti Vintage Hoodie",
        sizes=["S", "M", "L", "XL", "2XL"],
        reviews_channel="moonlight_shop_otzv",
        cargo_separate=True,
        adapted_style=True,
    )

    assert "✈️ AVIA: 14.000 so'm / 100g (7–9 kun)" in caption
    assert "🚗 AVTO: 10.000 so'm / 100g (14–18 kun)" in caption
    assert "✔️ Otzivlar: @moonlight_shop_otzv" in caption
    assert "@MOONLIGHT_ADMINNN" in caption


@pytest.mark.asyncio
async def test_customer_photo_not_intercepted_by_admin_import(test_db_session):
    """
    Verifies that non-admin customer receipt photos are NOT intercepted by
    admin.handle_importable_post, ensuring they can reach orders.router.
    """
    from bot.handlers.admin import is_admin_message, is_importable_message
    from aiogram.types import Message, PhotoSize, User as TgUser

    customer_id = 1122334455
    admin_id = 9988776655

    async with test_db_session() as session:
        session.add(Admin(telegram_id=admin_id, name="Shop Admin", role="admin"))
        await session.commit()

    # Create customer photo message
    customer_msg = MagicMock(spec=Message)
    customer_msg.from_user = MagicMock(spec=TgUser)
    customer_msg.from_user.id = customer_id
    customer_msg.photo = [MagicMock(spec=PhotoSize)]
    customer_msg.caption = None
    customer_msg.text = None
    customer_msg.forward_origin = None
    customer_msg.forward_from_chat = None
    customer_msg.forward_date = None

    # is_importable_message returns True because photo exists
    assert is_importable_message(customer_msg) is True

    # BUT is_admin_message filter returns False for customer
    with patch("bot.handlers.admin.async_session_factory", test_db_session):
        assert await is_admin_message(customer_msg) is False

    # For admin, is_admin_message returns True
    admin_msg = MagicMock(spec=Message)
    admin_msg.from_user = MagicMock(spec=TgUser)
    admin_msg.from_user.id = admin_id
    admin_msg.photo = [MagicMock(spec=PhotoSize)]
    admin_msg.caption = None
    admin_msg.text = None
    admin_msg.forward_origin = None
    admin_msg.forward_from_chat = None
    admin_msg.forward_date = None

    with patch("bot.handlers.admin.async_session_factory", test_db_session):
        assert await is_admin_message(admin_msg) is True


@pytest.mark.asyncio
async def test_admin_orders_callback_display(test_db_session):
    """Tests the admin_orders inline callback displaying recent orders."""
    from bot.handlers.admin import handle_admin_orders
    from db.models import Order

    async with test_db_session() as session:
        session.add(
            Order(
                user_id=1001,
                customer_name="Dilnoza",
                items_snapshot=[{"product_id": 1, "title": "Pushti Hoodie", "price": 120000, "qty": 1}],
                total=120000,
                status="pending_approval",
            )
        )
        await session.commit()

    cb = MagicMock()
    cb.data = "admin_orders"
    cb.message = MagicMock()
    cb.message.edit_text = AsyncMock()
    cb.answer = AsyncMock()

    with patch("bot.handlers.admin.async_session_factory", test_db_session):
        await handle_admin_orders(cb)

    cb.message.edit_text.assert_called_once()
    called_text = cb.message.edit_text.call_args.args[0]
    assert "Oxirgi buyurtmalar" in called_text
    assert "Dilnoza" in called_text
    assert "120.000 so'm" in called_text
    assert "Tasdiqlash kutilmoqda" in called_text
    cb.answer.assert_called_once()


@pytest.mark.asyncio
async def test_admin_menu_navigation_callbacks():
    """Tests admin menu navigation callbacks admin_menu, admin_main_menu, admin_done."""
    from bot.handlers.admin import handle_return_admin_menu

    for cb_data in ["admin_menu", "admin_main_menu", "admin_done"]:
        cb = MagicMock()
        cb.data = cb_data
        cb.message = MagicMock()
        cb.message.edit_text = AsyncMock()
        cb.answer = AsyncMock()
        mock_state = AsyncMock()

        await handle_return_admin_menu(cb, state=mock_state)

        mock_state.clear.assert_called_once()
        cb.message.edit_text.assert_called_once()
        assert "Admin Paneli" in cb.message.edit_text.call_args.args[0]
        cb.answer.assert_called_once()


@pytest.mark.asyncio
async def test_admin_broadcast_flow(test_db_session):
    """Tests starting broadcast and sending broadcast message to customers."""
    from bot.handlers.admin import handle_admin_broadcast_start, process_broadcast_message, AdminSettingsState
    from db.models import User

    # 1. Start broadcast
    cb = MagicMock()
    cb.message = MagicMock()
    cb.message.edit_text = AsyncMock()
    cb.answer = AsyncMock()
    mock_state = AsyncMock()

    await handle_admin_broadcast_start(cb, mock_state)
    mock_state.set_state.assert_called_once_with(AdminSettingsState.waiting_for_broadcast_text)
    assert "Broadcast" in cb.message.edit_text.call_args.args[0]

    # 2. Process broadcast
    admin_id = 9988776655
    async with test_db_session() as session:
        session.add(Admin(telegram_id=admin_id, name="Admin", role="admin"))
        session.add(User(telegram_id=111, name="U1"))
        session.add(User(telegram_id=222, name="U2"))
        await session.commit()

    msg = MagicMock()
    msg.from_user = MagicMock()
    msg.from_user.id = admin_id
    msg.photo = None
    msg.text = "Yangiliklar va Chegirmalar! 🌸"
    status_mock = MagicMock()
    status_mock.edit_text = AsyncMock()
    msg.answer = AsyncMock(return_value=status_mock)

    with patch("bot.handlers.admin.async_session_factory", test_db_session):
        with patch("bot.handlers.admin.is_user_admin", AsyncMock(return_value=True)):
            with patch("bot.loader.bot") as mock_bot:
                mock_bot.send_message = AsyncMock()
                mock_state_proc = AsyncMock()

                await process_broadcast_message(msg, mock_state_proc)

                mock_state_proc.clear.assert_called_once()
                assert mock_bot.send_message.call_count == 2
                status_mock.edit_text.assert_called_once()
                summary_output = status_mock.edit_text.call_args.args[0]
                assert "Yetkazildi: <b>2</b>" in summary_output


@pytest.mark.asyncio
async def test_admin_reset_confirm_safely_guarded():
    """Tests that admin_reset_confirm safely refuses to reset data."""
    from bot.handlers.admin import handle_admin_reset_confirm

    cb = MagicMock()
    cb.data = "admin_reset_confirm"
    cb.answer = AsyncMock()

    await handle_admin_reset_confirm(cb)
    cb.answer.assert_called_once()
    assert "xavfsizlik" in cb.answer.call_args.args[0]
    assert cb.answer.call_args.kwargs.get("show_alert") is True


def test_order_notifier_centralized_emojis():
    """Verifies order_notifier uses verified emojis from premium_emojis."""
    import bot.services.order_notifier as on
    import bot.services.premium_emojis as pe

    assert on.TG_MOON == pe.TG_MOON
    assert on.TG_SAKURA == pe.TG_SAKURA
    assert on.TG_MONEY == pe.TG_MONEY
    assert on.TG_PRODUCT == pe.TG_PRODUCT
    assert on.TG_TIME == pe.TG_TIME
    assert "5440354006335495210" in on.TG_SAKURA


@pytest.mark.asyncio
async def test_admin_manual_wizard_multi_photo_not_hijacked():
    """
    Verifies that when an admin is in ProductWizard.photos, uploading photos
    delegates to process_wizard_photo and appends to the photo list rather than
    prematurely hijacking the flow into ProductWizard.price.
    """
    from bot.handlers.admin import handle_importable_post, ProductWizard
    from aiogram.fsm.storage.memory import MemoryStorage
    from aiogram.fsm.context import FSMContext
    from aiogram.fsm.storage.base import StorageKey

    storage = MemoryStorage()
    key = StorageKey(bot_id=1, chat_id=99887766, user_id=99887766)
    state = FSMContext(storage=storage, key=key)
    await state.set_state(ProductWizard.photos)
    await state.update_data(photos=[])

    msg = MagicMock()
    msg.from_user = MagicMock()
    msg.from_user.id = 99887766
    msg.photo = [MagicMock(file_id="photo_step1_1")]
    msg.caption = None
    msg.text = None
    msg.forward_origin = None
    msg.forward_from_chat = None
    msg.forward_date = None
    msg.media_group_id = None
    msg.answer = AsyncMock()

    with patch("bot.handlers.admin.is_user_admin", AsyncMock(return_value=True)):
        await handle_importable_post(msg, state)

    # Must have appended the photo to state data
    data = await state.get_data()
    assert "photo_step1_1" in data.get("photos", [])
    # State MUST remain in ProductWizard.photos for subsequent photos!
    cur_state = await state.get_state()
    assert cur_state == ProductWizard.photos.state
    # Message confirmed photo added
    msg.answer.assert_called_once()
    assert "Rasm qo'shildi" in msg.answer.call_args[0][0]


@pytest.mark.asyncio
async def test_admin_broadcast_with_retry_after(test_db_session):
    """Verifies broadcast handles TelegramRetryAfter exception and retries gracefully."""
    from bot.handlers.admin import process_broadcast_message
    from db.models import User
    from aiogram.exceptions import TelegramRetryAfter

    admin_id = 9988776655
    async with test_db_session() as session:
        session.add(Admin(telegram_id=admin_id, name="Admin", role="admin"))
        session.add(User(telegram_id=555, name="U555"))
        await session.commit()

    msg = MagicMock()
    msg.from_user = MagicMock()
    msg.from_user.id = admin_id
    msg.photo = None
    msg.text = "Maxsus e'lon! 🌸"
    status_mock = MagicMock()
    status_mock.edit_text = AsyncMock()
    msg.answer = AsyncMock(return_value=status_mock)

    mock_bot = AsyncMock()
    retry_exc = TelegramRetryAfter(method=MagicMock(), message="Too many requests", retry_after=0.01)
    # First call raises TelegramRetryAfter, second call succeeds
    mock_bot.send_message.side_effect = [retry_exc, AsyncMock()]

    with patch("bot.handlers.admin.async_session_factory", test_db_session), \
         patch("bot.handlers.admin.is_user_admin", AsyncMock(return_value=True)), \
         patch("bot.loader.bot", mock_bot), \
         patch("asyncio.sleep", AsyncMock()):
        mock_state = AsyncMock()
        await process_broadcast_message(msg, mock_state)

        assert mock_bot.send_message.call_count == 2
        status_mock.edit_text.assert_called_once()
        summary_output = status_mock.edit_text.call_args.args[0]
        assert "Yetkazildi: <b>1</b>" in summary_output



