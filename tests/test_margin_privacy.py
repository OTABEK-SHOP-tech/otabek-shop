import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message, CallbackQuery, Chat, User
from sqlalchemy import select

from api.services.formatters import (
    build_channel_caption,
    strip_private_pricing_data,
    calculate_retail_price,
    parse_channel_post,
    format_price,
)
from bot.handlers.admin import (
    handle_import_margin_select,
    build_product_import_summary_text,
    build_product_import_summary_keyboard,
    MARGIN_PERCENT_OPTIONS,
)
from bot.services.channel_post import post_product_to_channel
from db.models import Product, Setting


def test_margin_options_include_critical_percentages():
    """Verify that percentage buttons include 20%, 35%, 50%, and others."""
    assert 20 in MARGIN_PERCENT_OPTIONS
    assert 35 in MARGIN_PERCENT_OPTIONS
    assert 50 in MARGIN_PERCENT_OPTIONS
    assert 30 in MARGIN_PERCENT_OPTIONS
    assert 100 in MARGIN_PERCENT_OPTIONS


def test_automatic_retail_price_calculation_for_percentage_buttons():
    """
    When admin clicks a percentage button (e.g. 20%, 35%, 50%),
    the retail price is automatically calculated as source_price * (1 + margin / 100)
    rounded to clean 1,000 so'm.
    """
    source_price = 50000

    # 20%: 50.000 * 1.20 = 60.000
    retail_20 = calculate_retail_price(source_price, margin_percent=20.0, clamp=False)
    assert retail_20 == 60000

    # 35%: 50.000 * 1.35 = 67.500 -> rounded to clean 68.000
    retail_35 = calculate_retail_price(source_price, margin_percent=35.0, clamp=False)
    assert retail_35 == 68000

    # 50%: 50.000 * 1.50 = 75.000
    retail_50 = calculate_retail_price(source_price, margin_percent=50.0, clamp=False)
    assert retail_50 == 75000

    # 10%: 50.000 * 1.10 = 55.000
    retail_10 = calculate_retail_price(source_price, margin_percent=10.0, clamp=False)
    assert retail_10 == 55000

    # 100%: 50.000 * 2.00 = 100.000
    retail_100 = calculate_retail_price(source_price, margin_percent=100.0, clamp=False)
    assert retail_100 == 100000


@pytest.mark.asyncio
async def test_handle_import_margin_select_flow():
    """
    Clicking a percentage button:
    1. Recalculates retail price in FSM state.
    2. Updates preview message with highlighted button and privacy note.
    3. Sends private toast answer to the clicking admin only.
    """
    storage = MemoryStorage()
    state = FSMContext(storage=storage, key=MagicMock())
    await state.set_data({
        "source_price": 50000,
        "price": 65000,
        "margin_percent": 30,
        "category": "hoodie",
        "title": "Pushti Hoodie 🌸",
        "photos": ["photo1.jpg"],
        "sizes": ["S", "M", "L"],
    })

    callback = MagicMock(spec=CallbackQuery)
    callback.data = "wizard_margin_35"
    callback.answer = AsyncMock()
    callback.message = MagicMock(spec=Message)
    callback.message.caption = "Old caption"
    callback.message.edit_caption = AsyncMock()

    await handle_import_margin_select(callback, state)

    # State updated with 35% margin: 50.000 * 1.35 = 67.500 -> 68.000
    data = await state.get_data()
    assert data["margin_percent"] == 35
    assert data["price"] == 68000
    assert data["source_price"] == 50000

    # Toast callback answer sent with new retail price
    callback.answer.assert_called_once_with("Foyda marjasi: 35% (68.000 so'm)")

    # Edit caption called
    callback.message.edit_caption.assert_called_once()
    caption_arg = callback.message.edit_caption.call_args.kwargs["caption"]

    # Preview card shows supplier price and profit percentage to admin privately
    assert "Asl narxi (ta'minotchi):</b> 50.000 so'm" in caption_arg
    assert "Sotuv narxi (+35%):</b> <b>68.000 so'm</b>" in caption_arg
    # Explicit privacy reassurance is present
    assert "Maxfiylik: Asl narxi va foyda foizi faqat sizga ko'rinadi" in caption_arg


def test_channel_caption_never_shows_profit_or_supplier_price():
    """
    CRITICAL PRIVACY TEST:
    In build_channel_caption, NEVER show profit percentage or supplier price!
    Customers in the channel must ONLY see the clean retail price.
    """
    caption = build_channel_caption(
        category_slug="hoodie",
        price=68000,
        cargo_rate_avia=14000,
        cargo_rate_avto=10000,
        title="Pushti Vintage Hoodie",
        sizes=["S", "M", "L"],
        reviews_channel="moonlight_shop_otzv",
        adapted_style=True,
        source_price=50000,       # passed explicitly
        margin_percent=35.0,      # passed explicitly
    )

    # Must contain clean retail price
    assert "🎟️ <b>Narx:</b> 68.000 so'm" in caption

    # Must NEVER contain supplier price or profit margin
    assert "50.000" not in caption
    assert "Asl narxi" not in caption
    assert "asl narx" not in caption.lower()
    assert "ta'minotchi" not in caption.lower()
    assert "35%" not in caption
    assert "foyda" not in caption.lower()
    assert "marja" not in caption.lower()
    assert "+35%" not in caption


def test_strip_private_pricing_data_from_dirty_title():
    """
    If a product title contains embedded supplier price or profit percentages,
    strip_private_pricing_data removes them cleanly.
    """
    dirty_titles = [
        ("Pushti Vintage Hoodie (+35% foyda)", "Pushti Vintage Hoodie"),
        ("Ko'ylak (Asl narxi: 50.000 so'm, +30% foyda)", "Ko'ylak"),
        ("Sviter (Ta'minotchi narxi: 45.000 so'm)", "Sviter"),
        ("Hudi 35% foyda bilan", "Hudi bilan"),
        ("Kurtka (+50%)", "Kurtka"),
        ("Shim (Foyda: 30%)", "Shim"),
        ("Sumka (Tannarx: 40000 so'm)", "Sumka"),
    ]

    for dirty, expected_clean in dirty_titles:
        cleaned = strip_private_pricing_data(dirty)
        assert cleaned == expected_clean
        assert "foyda" not in cleaned.lower()
        assert "asl narx" not in cleaned.lower()
        assert "ta'minotchi" not in cleaned.lower()
        assert "%" not in cleaned


def test_build_channel_caption_sanitizes_dirty_title():
    """
    Even if an admin imports or sets a title with supplier price or profit margin,
    build_channel_caption strips them completely before outputting to the channel.
    """
    caption = build_channel_caption(
        category_slug="hoodie",
        price=70000,
        title="Pushti Hoodie (+35% foyda, Asl narxi: 50.000 so'm)",
        adapted_style=True,
    )

    # Title in caption must be clean
    assert "✨ <b>Pushti Hoodie</b>" in caption
    assert "35%" not in caption
    assert "foyda" not in caption.lower()
    assert "50.000" not in caption
    assert "asl narxi" not in caption.lower()
    assert "🎟️ <b>Narx:</b> 70.000 so'm" in caption


@pytest.mark.asyncio
async def test_post_product_to_channel_strict_privacy(test_db_session):
    """
    End-to-end post_product_to_channel test:
    Verify that the caption sent to the channel has only the clean retail price
    and strictly 0 supplier price or profit margin leaks.
    """
    async with test_db_session() as session:
        prod = Product(
            title="Elegant Ko'ylak (+35% foyda)",
            price=70000,
            source_price=50000,
            category="dress",
            photos=["clean_dress.jpg"],
            sizes=["S", "M", "L"],
        )
        session.add(prod)
        res_ch = await session.execute(select(Setting).where(Setting.key == "channel_id"))
        ch = res_ch.scalars().first()
        if ch:
            ch.value = "@moonlight_chinese_shop"
        else:
            session.add(Setting(key="channel_id", value="@moonlight_chinese_shop"))
        await session.commit()

    captured_kwargs = {}

    async def fake_send_photo(*args, **kwargs):
        captured_kwargs.update(kwargs)
        msg = MagicMock()
        msg.message_id = 999
        return msg

    with patch("bot.services.channel_post.async_session_factory", test_db_session), \
         patch("bot.services.channel_post.bot") as mock_bot:
        mock_bot.get_me = AsyncMock(return_value=MagicMock(username="moonlight_chinese_bot"))
        mock_bot.send_photo = AsyncMock(side_effect=fake_send_photo)

        res = await post_product_to_channel(prod)
        assert res["success"] is True

    caption = captured_kwargs.get("caption", "")
    assert "70.000 so'm" in caption
    assert "50.000" not in caption
    assert "Asl narxi" not in caption
    assert "asl narx" not in caption.lower()
    assert "35%" not in caption
    assert "foyda" not in caption.lower()
    assert "ta'minotchi" not in caption.lower()


def test_parse_channel_post_does_not_leak_supplier_price_into_title():
    """
    When parsing forwarded supplier text, the supplier price or margin
    must NOT be assigned as the product title.
    """
    supplier_post = (
        "#kurtka 🌸\n"
        "Asl narxi: 90.000 so'm\n"
        "Foyda: 35%\n"
        "Razmer: S-2XL\n"
        "Kargo: 10.000 so'm\n"
    )

    parsed = parse_channel_post(supplier_post, apply_margin=True)
    assert parsed["source_price"] == 90000
    # Title must NOT be 'Asl narxi: 90.000 so'm' or 'Foyda: 35%'!
    assert parsed["title"] != "Asl narxi: 90.000 so'm"
    assert "asl narx" not in parsed["title"].lower()
    assert "foyda" not in parsed["title"].lower()
    assert "Kurtka" in parsed["title"]


def test_public_product_api_never_exposes_source_price():
    """
    Customer-facing API endpoints must NEVER expose source_price or formatted_source_price.
    Only admin endpoints with is_admin=True may see it.
    """
    from datetime import datetime, timezone
    from api.routes.products import enrich_product_out

    prod = Product(
        id=42,
        title="Pushti Hoodie (+35% foyda)",
        description="Qalin issiq kiyim. Asl narxi: 50.000 so'm, foyda: 35%",
        price=68000,
        source_price=50000,
        category="hoodie",
        photos=["p1.jpg"],
        sizes=["M", "L"],
        colors=["Pushti"],
        weight_grams=350,
        in_stock=True,
        is_new=True,
        is_hit=False,
        views=15,
        created_at=datetime.now(timezone.utc),
    )

    # 1. Customer facing (default is_admin=False)
    cust_out = enrich_product_out(prod, is_admin=False)
    assert cust_out.source_price is None
    assert cust_out.formatted_source_price is None
    # Title and description are sanitized of private pricing data
    assert "35%" not in cust_out.title
    assert "foyda" not in cust_out.title.lower()
    assert cust_out.title == "Pushti Hoodie"
    assert "Asl narxi" not in cust_out.description
    assert "50.000" not in cust_out.description
    assert "35%" not in cust_out.description
    assert cust_out.price == 68000
    assert cust_out.formatted_price == "68.000 so'm"

    # 2. Admin facing (is_admin=True)
    adm_out = enrich_product_out(prod, is_admin=True)
    assert adm_out.source_price == 50000
    assert adm_out.formatted_source_price == "50.000 so'm"
    assert adm_out.price == 68000


@pytest.mark.asyncio
async def test_handle_import_margin_select_back_calculates_if_source_missing():
    """
    If source_price was somehow missing or 0 in state,
    handle_import_margin_select correctly back-calculates source_price
    using current retail price and old margin, then applies new percentage.
    """
    storage = MemoryStorage()
    state = FSMContext(storage=storage, key=MagicMock())
    # 70.000 retail price with 35% margin -> source ~ 51.852
    await state.set_data({
        "source_price": 0,
        "price": 70000,
        "margin_percent": 35,
        "category": "jempir",
        "title": "Jempir 🌸",
    })

    callback = MagicMock(spec=CallbackQuery)
    callback.data = "wizard_margin_50"
    callback.answer = AsyncMock()
    callback.message = MagicMock(spec=Message)
    callback.message.caption = None
    callback.message.edit_text = AsyncMock()

    await handle_import_margin_select(callback, state)

    data = await state.get_data()
    assert data["margin_percent"] == 50
    assert data["source_price"] > 0
    # 51.852 * 1.50 = 77.778 -> rounded to 78.000
    assert data["price"] == 78000
    callback.answer.assert_called_once_with("Foyda marjasi: 50% (78.000 so'm)")

