import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from api.services.formatters import (
    build_channel_caption,
    is_non_clothing_category,
    NON_CLOTHING_CATEGORIES,
)
from bot.handlers.admin import (
    process_product_import,
    process_wizard_price,
    process_wizard_category,
    process_wizard_colors,
    ProductWizard,
    build_product_import_summary_text,
)


def test_non_clothing_categories_membership():
    assert "sumka" in NON_CLOTHING_CATEGORIES
    assert "aksessuar" in NON_CLOTHING_CATEGORIES
    assert "kosmetika" in NON_CLOTHING_CATEGORIES
    assert "wig" in NON_CLOTHING_CATEGORIES
    assert "scarf" in NON_CLOTHING_CATEGORIES
    assert "soat" in NON_CLOTHING_CATEGORIES
    assert "dekor" in NON_CLOTHING_CATEGORIES

    assert is_non_clothing_category("sumka") is True
    assert is_non_clothing_category("kosmetika") is True
    assert is_non_clothing_category("aksessuar") is True
    assert is_non_clothing_category("soat") is True
    assert is_non_clothing_category("dekor") is True
    assert is_non_clothing_category("wig") is True
    assert is_non_clothing_category("scarf") is True

    # Clothing / shoes must NOT be non-clothing
    assert is_non_clothing_category("hoodie") is False
    assert is_non_clothing_category("koylak") is False
    assert is_non_clothing_category("shoes") is False
    assert is_non_clothing_category("jempir") is False
    assert is_non_clothing_category("shim") is False


def test_channel_caption_non_clothing_formatting():
    # 1. Cosmetics with Standart size: awkward "Razmer: Standart" MUST be omitted
    caption_kosmetika = build_channel_caption(
        category_slug="kosmetika",
        price=85000,
        cargo_rate_avia=14000,
        cargo_rate_avto=10000,
        contact_username="MOONLIGHT_ADMINNN",
        title="Namlantiruvchi Krem",
        sizes=["Standart"],
        colors=["Oq 🤍"],
        adapted_style=True,
    )
    assert "Razmer:" not in caption_kosmetika
    assert "O'lcham:" not in caption_kosmetika
    assert "Namlantiruvchi Krem" in caption_kosmetika
    assert "Ranglar:</b> Oq 🤍" in caption_kosmetika

    # 2. Accessories with Standart size: awkward "Razmer: Standart" MUST be omitted
    caption_aksessuar = build_channel_caption(
        category_slug="aksessuar",
        price=45000,
        cargo_rate_avia=14000,
        cargo_rate_avto=10000,
        contact_username="MOONLIGHT_ADMINNN",
        title="Vintage Soch Qadag'ich",
        sizes=["Standart"],
        adapted_style=True,
    )
    assert "Razmer:" not in caption_aksessuar
    assert "O'lcham:" not in caption_aksessuar
    assert "Vintage Soch Qadag" in caption_aksessuar

    # 3. Bags with Standart size: shows clean "O'lcham: Standart"
    caption_sumka = build_channel_caption(
        category_slug="sumka",
        price=125000,
        cargo_rate_avia=14000,
        cargo_rate_avto=10000,
        contact_username="MOONLIGHT_ADMINNN",
        title="Katakli Vintage Sumka",
        sizes=["Standart"],
        adapted_style=True,
    )
    assert "O'lcham:</b> Standart" in caption_sumka
    assert "Razmer:" not in caption_sumka

    # 4. Clothing (hoodie): displays standard "Razmer: S-2XL"
    caption_hoodie = build_channel_caption(
        category_slug="hoodie",
        price=180000,
        cargo_rate_avia=14000,
        cargo_rate_avto=10000,
        contact_username="MOONLIGHT_ADMINNN",
        title="Vintage Hoodie",
        sizes=["S", "M", "L", "XL", "2XL"],
        adapted_style=True,
    )
    assert "Razmer:</b> S-2XL" in caption_hoodie


@pytest.mark.asyncio
async def test_informative_screenshot_non_clothing_fast_track():
    """
    Path A: When admin sends screenshot of bag/cosmetics with price detected by vision,
    the bot auto-defaults sizes to Standart, sets colors, and immediately displays
    show_product_import_summary without bothering admin with size questions!
    """
    msg = MagicMock()
    msg.from_user = MagicMock(id=8643984824)
    msg.answer = AsyncMock()

    mock_status_msg = MagicMock()
    mock_status_msg.delete = AsyncMock()
    msg.answer.return_value = mock_status_msg

    state = AsyncMock()
    state_data = {}

    async def mock_update_data(**kwargs):
        state_data.update(kwargs)

    async def mock_get_data():
        return state_data

    state.update_data.side_effect = mock_update_data
    state.get_data.side_effect = mock_get_data

    vision_data = {
        "success": True,
        "title": "Aesthetic Katakli Sumka",
        "category": "sumka",
        "source_price": 50000,
        "retail_price": 68000,
        "sizes": [],
        "colors": ["Qora-Oq 🖤"],
    }

    with patch("bot.handlers.admin.extract_product_from_image", AsyncMock(return_value=vision_data)), \
         patch("bot.handlers.admin.show_product_import_summary", AsyncMock()) as mock_summary:
        await process_product_import(
            message=msg,
            state=state,
            raw_text="Import",
            photos=[b"bag_screenshot_bytes"],
            source_label="AI Vision Boost",
        )

        mock_summary.assert_called_once()
        assert state_data["category"] == "sumka"
        assert state_data["sizes"] == ["Standart"]
        assert "Qora-Oq 🖤" in state_data["colors"]
        assert state_data["price"] == 68000


@pytest.mark.asyncio
async def test_plain_photo_non_clothing_skips_sizes_prompt():
    """
    Path B: Admin sends plain photo of sumka (price not in photo).
    Vision extracts category 'sumka' but source_price=0.
    Bot prompts for price (1-qadam).
    When admin enters '35 yuan', the bot skips sizes and directly prompts for colors or shows summary!
    """
    msg = MagicMock()
    msg.from_user = MagicMock(id=8643984824)
    msg.answer = AsyncMock()
    mock_status_msg = MagicMock()
    mock_status_msg.delete = AsyncMock()
    msg.answer.return_value = mock_status_msg

    state = AsyncMock()
    state_data = {}

    async def mock_update_data(**kwargs):
        state_data.update(kwargs)

    async def mock_get_data():
        return state_data

    state.update_data.side_effect = mock_update_data
    state.get_data.side_effect = mock_get_data

    vision_data = {
        "success": True,
        "title": "Katakli Sumka",
        "category": "sumka",
        "source_price": 0,
        "retail_price": 0,
        "sizes": [],
        "colors": ["Qora-Oq 🖤"],
    }

    with patch("bot.handlers.admin.extract_product_from_image", AsyncMock(return_value=vision_data)):
        await process_product_import(
            message=msg,
            state=state,
            raw_text="",
            photos=[b"plain_bag_photo"],
            source_label="Rasm orqali import",
        )

        # Bot asks for price (1-qadam)
        state.set_state.assert_called_with(ProductWizard.price)
        assert state_data["category"] == "sumka"
        assert state_data["sizes"] == ["Standart"]

    # Now simulate admin typing '35 yuan'
    price_msg = MagicMock()
    price_msg.text = "35 yuan"
    price_msg.from_user = MagicMock(id=8643984824)
    price_msg.answer = AsyncMock()

    with patch("bot.handlers.admin.show_product_import_summary", AsyncMock()) as mock_summary:
        await process_wizard_price(price_msg, state)

        # Because category is 'sumka' and colors was already extracted ('Qora-Oq 🖤'),
        # it skips sizes AND colors and directly calls show_product_import_summary!
        mock_summary.assert_called_once()
        assert state_data["sizes"] == ["Standart"]
        assert state_data["price"] > 0


@pytest.mark.asyncio
async def test_plain_photo_quick_category_picker_then_skip_sizes():
    """
    Path B2: Admin sends photo where vision could not detect category (category='kiyim' default).
    Admin inputs price -> Bot asks to select category.
    Admin taps 'cat_pick_kosmetika' -> Bot sets sizes=['Standart'] and skips sizes, asking colors.
    """
    state = AsyncMock()
    state_data = {
        "photos": ["photo1"],
        "source_label": "Rasm orqali import",
        "category": "kiyim",
        "sizes": [],
        "colors": [],
    }

    async def mock_update_data(**kwargs):
        state_data.update(kwargs)

    async def mock_get_data():
        return state_data

    state.update_data.side_effect = mock_update_data
    state.get_data.side_effect = mock_get_data

    price_msg = MagicMock()
    price_msg.text = "45.000 so'm"
    price_msg.from_user = MagicMock(id=8643984824)
    price_msg.answer = AsyncMock()

    await process_wizard_price(price_msg, state)

    # Prompted quick category selection
    state.set_state.assert_called_with(ProductWizard.category)
    assert "Kategoriyani tanlang" in price_msg.answer.call_args.args[0]

    # Admin taps 'cat_pick_kosmetika'
    cb = MagicMock()
    cb.data = "cat_pick_kosmetika"
    cb.message = MagicMock()
    cb.message.answer = AsyncMock()
    cb.answer = AsyncMock()

    await process_wizard_category(cb, state)

    # Sizes must be automatically Standart and wizard moves to colors!
    assert state_data["category"] == "kosmetika"
    assert state_data["sizes"] == ["Standart"]
    state.set_state.assert_called_with(ProductWizard.colors)
    assert "ranglarini kiriting" in cb.message.answer.call_args.args[0].lower()


@pytest.mark.asyncio
async def test_admin_never_sees_silence_on_photo_arrival():
    """
    Verifies that when photos arrive, an immediate feedback message
    '🔄 Rasm tahlil qilinmoqda...' is sent to the chat before any heavy processing.
    """
    msg = MagicMock()
    msg.from_user = MagicMock(id=8643984824)
    msg.answer = AsyncMock()
    mock_status_msg = MagicMock()
    mock_status_msg.delete = AsyncMock()
    msg.answer.return_value = mock_status_msg

    state = AsyncMock()
    state.get_data.return_value = {}

    with patch("bot.handlers.admin.extract_product_from_image", AsyncMock(return_value={"success": False})), \
         patch("bot.handlers.admin.show_product_import_summary", AsyncMock()):
        await process_product_import(
            message=msg,
            state=state,
            raw_text="",
            photos=[b"some_photo_bytes"],
            source_label="Rasm import",
        )

        # The first message sent must be the loading/status message
        msg.answer.assert_any_call("🔄 <i>Rasm tahlil qilinmoqda va ma'lumotlar o'qilmoqda...</i> 🌸")
