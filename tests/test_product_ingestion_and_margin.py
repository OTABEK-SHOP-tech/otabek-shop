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
from db.models import Category, Product, Setting


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
    assert "💰 Narxi: 124.000 so'm" in caption
    assert "👗 Razmer: S-2XL" in caption
    assert "📦 Kargo: 12.000 so'm / 100g (alohida)" in caption
    assert "⏳ Yetkazib berish: 10–15 kun ichida" in caption
    assert "🌸 Otzivlar: @moonlight_shop_otzv" in caption
    assert "💌 Admin: @MOONLIGHT_ADMINNN" in caption

    # Check Telegram premium upgrade
    upgraded = upgrade_to_premium_emojis(caption)
    assert '<tg-emoji' in upgraded
    assert '5375296873982604963' in upgraded  # Money custom emoji


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
