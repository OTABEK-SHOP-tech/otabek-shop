import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message, CallbackQuery
from sqlalchemy import select

from api.services.formatters import strip_private_pricing_data, build_channel_caption, format_price
from bot.handlers.admin import (
    handle_import_margin_select,
    build_product_import_summary_text,
    build_product_import_summary_keyboard,
    MARGIN_PERCENT_OPTIONS,
)
from db.models import Product, Setting


def test_fabric_and_quality_percentages_preserved():
    """Harmless product descriptions with percentage must NEVER be corrupted."""
    assert strip_private_pricing_data("100% paxta") == "100% paxta"
    assert strip_private_pricing_data("Tarkibi: 95% paxta, 5% elastan") == "Tarkibi: 95% paxta, 5% elastan"
    assert strip_private_pricing_data("100% original") == "100% original"
    assert strip_private_pricing_data("100% sifatli") == "100% sifatli"
    assert strip_private_pricing_data("50% jun, 50% akril") == "50% jun, 50% akril"


def test_profit_in_sum_amounts_stripped():
    """Profit expressed as sum amount (not just %) must be cleanly stripped."""
    assert strip_private_pricing_data("Ko'ylak (Foyda: 20.000 so'm)") == "Ko'ylak"
    assert strip_private_pricing_data("Ko'ylak (20.000 so'm foyda)") == "Ko'ylak"
    assert strip_private_pricing_data("Ko'ylak (Foydasi: 15.000 so'm)") == "Ko'ylak"
    assert strip_private_pricing_data("Ko'ylak (Sof foyda: 25.000 so'm)") == "Ko'ylak"
    assert strip_private_pricing_data("Ko'ylak (Ustama: 20.000 so'm)") == "Ko'ylak"


def test_russian_and_chinese_wholesale_supplier_terms_stripped():
    """Russian and Chinese wholesale pricing tags must be stripped."""
    assert strip_private_pricing_data("Ko'ylak (Оптом 50000 сум)") == "Ko'ylak"
    assert strip_private_pricing_data("Ko'ylak (Опт: 50000 сум)") == "Ko'ylak"
    assert strip_private_pricing_data("Ko'ylak (Закупка: 4500 руб)") == "Ko'ylak"
    assert strip_private_pricing_data("Ko'ylak (Закуп: 5000)") == "Ko'ylak"
    assert strip_private_pricing_data("Ko'ylak 进货价: 35元") == "Ko'ylak"
    assert strip_private_pricing_data("Ko'ylak 成本: 35元") == "Ko'ylak"
    assert strip_private_pricing_data("Ko'ylak 批发价: 40") == "Ko'ylak"


def test_uzbek_supplier_spelling_variations_stripped():
    """Variations like narhi, optom 40k, optom 40 ming must be stripped."""
    assert strip_private_pricing_data("Ko'ylak Asl narhi: 50.000 so'm") == "Ko'ylak"
    assert strip_private_pricing_data("Ko'ylak (Tan narhi: 45000)") == "Ko'ylak"
    assert strip_private_pricing_data("Ko'ylak (optom 40k)") == "Ko'ylak"
    assert strip_private_pricing_data("Ko'ylak (optom 40 ming)") == "Ko'ylak"
    assert strip_private_pricing_data("Ko'ylak (Optom: 40.000 so'm)") == "Ko'ylak"


def test_channel_caption_paragraph_breaks_preserved():
    """Channel caption structure with blockquote paragraphs must not be collapsed."""
    caption = build_channel_caption(
        category_slug="koylak",
        price=70000,
        title="Elegant Ko'ylak",
        adapted_style=True,
    )
    cleaned = strip_private_pricing_data(caption)
    assert "\n\n<blockquote>" in cleaned
    assert "</blockquote>\n\n" in cleaned


def test_multiline_supplier_text_cleans_without_blank_gap():
    """When supplier price and margin lines are stripped from multiline text, no empty gap is left."""
    text = (
        "#kurtka 🌸\n"
        "Asl narxi: 90.000 so'm\n"
        "Foyda: 35%\n"
        "Razmer: S-2XL\n"
        "Kargo: 10.000 so'm"
    )
    cleaned = strip_private_pricing_data(text)
    assert "90.000" not in cleaned
    assert "35%" not in cleaned
    assert "Asl narxi" not in cleaned
    assert "Foyda" not in cleaned
    assert cleaned == "#kurtka 🌸\nRazmer: S-2XL\nKargo: 10.000 so'm"


def test_admin_preview_card_shows_profit_calculation():
    """
    In the admin preview card, the admin can clearly see how much profit
    is being made (in so'm and %), while customer channel captions never show it.
    """
    data = {
        "title": "Pushti Hoodie",
        "category": "hoodie",
        "source_price": 50000,
        "price": 68000,
        "margin_percent": 35,
        "sizes": ["S", "M"],
        "colors": ["Pushti"],
        "photos": ["p1.jpg"],
    }
    summary = build_product_import_summary_text(data)

    # Admin preview card must show:
    # 1. Asl narxi
    assert "Asl narxi (ta'minotchi):</b> 50.000 so'm" in summary
    # 2. Sotuv narxi with margin percentage
    assert "Sotuv narxi (+35%):</b> <b>68.000 so'm</b>" in summary
    # 3. Exact net profit in so'm (68.000 - 50.000 = 18.000 so'm)
    assert "18.000 so'm" in summary
    # 4. Privacy reassurance note
    assert "Maxfiylik: Asl narxi va foyda foizi faqat sizga ko'rinadi" in summary


@pytest.mark.asyncio
async def test_customer_start_deep_link_never_leaks_pricing_notes(test_db_session):
    """
    When customer invokes /start product_{id}, even if product in DB has dirty pricing notes,
    the customer message strictly sanitizes them and only displays retail price.
    """
    from bot.handlers.start import handle_start
    from aiogram.filters import CommandObject
    from db.models import Category

    async with test_db_session() as session:
        cat = Category(slug="vintage_dress", name="Vintage", emoji="👗", sort_order=99)
        session.add(cat)
        prod = Product(
            id=7777,
            title="Vintage Dress (+35% foyda)",
            description="Ta'minotchi narxi: 50.000 so'm, +35% foyda. 100% paxta.",
            price=68000,
            source_price=50000,
            category="vintage_dress",
            photos=[],
            sizes=["S", "M"],
        )
        session.add(prod)
        await session.commit()

    msg = MagicMock()
    msg.from_user = MagicMock(id=112233, full_name="Customer", username="cust")
    msg.answer = AsyncMock()
    msg.answer_photo = AsyncMock()

    cmd = CommandObject(prefix="/", command="start", args="product_7777")

    with patch("bot.handlers.start.async_session_factory", test_db_session):
        await handle_start(msg, cmd)

    assert msg.answer.call_count == 1
    sent_text = msg.answer.call_args[0][0]

    # Customer message must NOT contain supplier price or margin
    assert "50.000" not in sent_text
    assert "Ta'minotchi" not in sent_text
    assert "+35%" not in sent_text
    assert "foyda" not in sent_text.lower()
    # But clean retail price and harmless cotton composition MUST be present!
    assert "68.000 so'm" in sent_text
    assert "100% paxta" in sent_text

