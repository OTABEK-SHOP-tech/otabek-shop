import io
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from api.services.vision_ocr import (
    convert_currency_to_uzs,
    normalize_color,
    normalize_colors,
    normalize_sizes,
    normalize_category,
    parse_vision_response,
    extract_product_from_image,
)
from api.services.formatters import calculate_retail_price, calculate_margin_percent


# ============================================================================
# 1. CURRENCY CONVERSION & PROFIT MARGIN TESTS
# ============================================================================

def test_currency_conversion_chinese_yuan():
    # 35 Yuan at 1800 UZS/Yuan = 63,000 UZS
    assert convert_currency_to_uzs(35, "CNY") == 63000
    assert convert_currency_to_uzs(35, "¥") == 63000
    assert convert_currency_to_uzs(35, "￥") == 63000
    assert convert_currency_to_uzs(35, "yuan") == 63000
    assert convert_currency_to_uzs(35, "元") == 63000
    assert convert_currency_to_uzs(35, "块") == 63000
    assert convert_currency_to_uzs(29.9, "RMB") == 53820


def test_currency_conversion_usd():
    # $15 at 12900 UZS/USD = 193,500 UZS
    assert convert_currency_to_uzs(15, "USD") == 193500
    assert convert_currency_to_uzs(15, "$") == 193500
    assert convert_currency_to_uzs(25.5, "USD") == 328950


def test_currency_conversion_ruble():
    # 500 RUB at 140 UZS/RUB = 70,000 UZS
    assert convert_currency_to_uzs(500, "RUB") == 70000
    assert convert_currency_to_uzs(500, "₽") == 70000
    assert convert_currency_to_uzs(1200, "руб") == 168000
    assert convert_currency_to_uzs(1200, "рубль") == 168000


def test_currency_conversion_uzs():
    # Uzbek som is 1:1
    assert convert_currency_to_uzs(95000, "UZS") == 95000
    assert convert_currency_to_uzs(95000, "so'm") == 95000
    assert convert_currency_to_uzs(95000, "сум") == 95000
    assert convert_currency_to_uzs(95000, "сўм") == 95000


def test_currency_conversion_string_input():
    # String input should not raise TypeError
    assert convert_currency_to_uzs("35", "CNY") == 63000
    assert convert_currency_to_uzs("15.5", "USD") == 199950
    assert convert_currency_to_uzs("invalid", "USD") == 0


def test_currency_conversion_heuristics():
    # Small number without currency: default to Chinese Yuan
    assert convert_currency_to_uzs(28, None) == 28 * 1800
    # Large number without currency: default to Uzbek Som
    assert convert_currency_to_uzs(85000, None) == 85000
    # Zero or negative
    assert convert_currency_to_uzs(0, "CNY") == 0
    assert convert_currency_to_uzs(-10, "CNY") == 0


def test_tiered_profit_margin_on_converted_price():
    # 35 Yuan -> 63,000 UZS (< 80,000 -> 35% margin)
    src_cheap = convert_currency_to_uzs(35, "CNY")
    assert src_cheap == 63000
    assert calculate_margin_percent(src_cheap) == 35.0
    retail_cheap = calculate_retail_price(src_cheap)
    assert retail_cheap == 85000  # 63000 * 1.35 = 85050 -> 85000

    # 60 Yuan -> 108,000 UZS (80,000 - 200,000 -> 30% margin)
    src_mid = convert_currency_to_uzs(60, "CNY")
    assert src_mid == 108000
    assert calculate_margin_percent(src_mid) == 30.0
    retail_mid = calculate_retail_price(src_mid)
    assert retail_mid == 140000  # 108000 * 1.30 = 140400 -> 140000

    # 150 Yuan -> 270,000 UZS (> 200,000 -> 25% margin)
    src_exp = convert_currency_to_uzs(150, "CNY")
    assert src_exp == 270000
    assert calculate_margin_percent(src_exp) == 25.0
    retail_exp = calculate_retail_price(src_exp)
    assert retail_exp == 338000  # 270000 * 1.25 = 337500 -> 338000


# ============================================================================
# 2. MULTILINGUAL SIZE NORMALIZATION TESTS
# ============================================================================

def test_normalize_sizes_chinese():
    # 均码 / 一码 / 通码 / 大码 -> Standart
    assert normalize_sizes("均码") == ["Standart"]
    assert normalize_sizes(["均码"]) == ["Standart"]
    assert normalize_sizes(["一码"]) == ["Standart"]
    assert normalize_sizes(["通码"]) == ["Standart"]
    assert normalize_sizes(["大码"]) == ["Standart"]

    # Chinese sizes with 码 suffix
    assert normalize_sizes(["S码", "M码", "L码"]) == ["S", "M", "L"]
    assert normalize_sizes("S码, M码, L码") == ["S", "M", "L"]

    # Chinese shoe sizes with 码 suffix
    assert normalize_sizes(["36码", "37码", "38码", "39码"]) == ["36", "37", "38", "39"]

    # Chinese weight annotations in parentheses (e.g. Pinduoduo format)
    assert normalize_sizes(["M码 (建议100-115斤)", "L码 (建议115-130斤)"]) == ["M", "L"]
    assert normalize_sizes("均码（80-120斤）") == ["Standart"]
    assert normalize_sizes(["S码【建议90-105斤】", "M码【建议105-120斤】"]) == ["S", "M"]

    # Chinese prefix and range
    assert normalize_sizes("尺码: S-2XL") == ["S", "M", "L", "XL", "2XL"]
    assert normalize_sizes("尺码：S至2XL") == ["S", "M", "L", "XL", "2XL"]
    assert normalize_sizes("S-2XL码") == ["S", "M", "L", "XL", "2XL"]
    assert normalize_sizes("36-39") == ["36", "37", "38", "39"]


def test_normalize_sizes_russian():
    assert normalize_sizes("Стандарт") == ["Standart"]
    assert normalize_sizes(["Единый"]) == ["Standart"]
    assert normalize_sizes("S-XXL") == ["S", "M", "L", "XL", "2XL"]
    assert normalize_sizes(["42-45"]) == ["42", "43", "44", "45"]
    assert normalize_sizes(["42 размер", "44 размер"]) == ["42", "44"]


def test_normalize_sizes_english_and_uzbek():
    assert normalize_sizes("Free size") == ["Standart"]
    assert normalize_sizes("One size") == ["Standart"]
    assert normalize_sizes("Standart") == ["Standart"]
    assert normalize_sizes("Oversize") == ["Standart"]
    assert normalize_sizes(["S", "M", "L"]) == ["S", "M", "L"]
    assert normalize_sizes("S dan 2XL gacha") == ["S", "M", "L", "XL", "2XL"]


def test_normalize_sizes_empty_and_edge_cases():
    assert normalize_sizes("") == []
    assert normalize_sizes(None) == []
    assert normalize_sizes([]) == []


# ============================================================================
# 3. MULTILINGUAL COLOR TRANSLATION TESTS
# ============================================================================

def test_normalize_color_chinese():
    # Basic colors
    assert normalize_color("粉色") == "Pushti 🌸"
    assert normalize_color("白色") == "Oq 🤍"
    assert normalize_color("黑色") == "Qora 🖤"
    assert normalize_color("浅蓝") == "Havorang 🩵"
    assert normalize_color("米色") == "Bej 🤎"
    assert normalize_color("绿色") == "Yashil 💚"
    assert normalize_color("红色") == "Qizil ❤️"
    assert normalize_color("黄色") == "Sariq 💛"
    assert normalize_color("紫色") == "Binafsha 💜"
    assert normalize_color("灰色") == "Kulrang 🩶"
    assert normalize_color("棕色") == "Jigarrang 🤎"

    # Asian fashion trend colors
    assert normalize_color("奶茶色") == "Bej 🤎"
    assert normalize_color("驼色") == "Bej 🤎"
    assert normalize_color("燕麦色") == "Bej 🤎"
    assert normalize_color("焦糖色") == "Jigarrang 🤎"
    assert normalize_color("豆沙粉") == "Pushti 🌸"
    assert normalize_color("雾霾蓝") == "Havorang 🩵"
    assert normalize_color("牛仔蓝") == "Ko'k 💙"
    assert normalize_color("墨绿色") == "To'q yashil 💚"
    assert normalize_color("薄荷绿") == "Yalpiz rang 🌿"

    # With packaging or garment modifiers
    assert normalize_color("白色【加绒】") == "Oq 🤍"
    assert normalize_color("黑色单件") == "Qora 🖤"


def test_normalize_color_russian():
    assert normalize_color("розовый") == "Pushti 🌸"
    assert normalize_color("белый") == "Oq 🤍"
    assert normalize_color("черный") == "Qora 🖤"
    assert normalize_color("чёрный") == "Qora 🖤"
    assert normalize_color("голубой") == "Havorang 🩵"
    assert normalize_color("бежевый") == "Bej 🤎"
    assert normalize_color("зеленый") == "Yashil 💚"
    assert normalize_color("молочный") == "Krem rang 🍦"
    assert normalize_color("пудровый") == "Pushti 🌸"
    assert normalize_color("бордовый") == "To'q qizil ❤️"
    assert normalize_color("лавандовый") == "Binafsha 💜"
    assert normalize_color("персиковый") == "Shaftolirang 🍑"
    assert normalize_color("оливковый") == "Zaytun rang 🫒"


def test_normalize_color_english():
    assert normalize_color("pink") == "Pushti 🌸"
    assert normalize_color("white") == "Oq 🤍"
    assert normalize_color("black") == "Qora 🖤"
    assert normalize_color("light blue") == "Havorang 🩵"
    assert normalize_color("beige") == "Bej 🤎"
    assert normalize_color("cream") == "Krem rang 🍦"
    assert normalize_color("ivory") == "Krem rang 🍦"
    assert normalize_color("burgundy") == "To'q qizil ❤️"
    assert normalize_color("lavender") == "Binafsha 💜"
    assert normalize_color("peach") == "Shaftolirang 🍑"
    assert normalize_color("navy") == "To'q ko'k 💙"


def test_normalize_color_uzbek():
    assert normalize_color("pushti") == "Pushti 🌸"
    assert normalize_color("oq") == "Oq 🤍"
    assert normalize_color("qora") == "Qora 🖤"
    assert normalize_color("havorang") == "Havorang 🩵"
    assert normalize_color("bej") == "Bej 🤎"
    assert normalize_color("shaftolirang") == "Shaftolirang 🍑"


def test_normalize_colors_list_and_string():
    raw_str = "粉色, 白色, 黑色"
    assert normalize_colors(raw_str) == ["Pushti 🌸", "Oq 🤍", "Qora 🖤"]

    raw_list = ["розовый", "черный", "белый"]
    assert normalize_colors(raw_list) == ["Pushti 🌸", "Qora 🖤", "Oq 🤍"]

    # Pre-emoji preservation
    assert normalize_colors(["Pushti 🌸", "Oq 🤍"]) == ["Pushti 🌸", "Oq 🤍"]


# ============================================================================
# 4. MULTILINGUAL CATEGORY MAPPING TESTS
# ============================================================================

def test_normalize_category_multilingual():
    # Chinese
    assert normalize_category("卫衣") == "hoodie"
    assert normalize_category("连衣裙") == "koylak"
    assert normalize_category("包包") == "sumka"
    assert normalize_category("鞋子") == "shoes"
    assert normalize_category("毛衣") == "jempir"
    assert normalize_category("裤子") == "shim"
    assert normalize_category("短袖") == "futbolka"
    assert normalize_category("外套") == "kurtka"
    assert normalize_category("大衣") == "palto"
    assert normalize_category("假发") == "wig"

    # Russian
    assert normalize_category("худи") == "hoodie"
    assert normalize_category("толстовка") == "hoodie"
    assert normalize_category("платье") == "koylak"
    assert normalize_category("сумка") == "sumka"
    assert normalize_category("кроссовки") == "shoes"
    assert normalize_category("ботинки") == "shoes"
    assert normalize_category("лоферы") == "shoes"
    assert normalize_category("свитер") == "jempir"
    assert normalize_category("кардиган") == "jempir"

    # English & Uzbek
    assert normalize_category("hoodie") == "hoodie"
    assert normalize_category("dress") == "koylak"
    assert normalize_category("bag") == "sumka"
    assert normalize_category("shoes") == "shoes"
    assert normalize_category("poyabzal") == "shoes"
    assert normalize_category("krossovka") == "shoes"
    assert normalize_category("tufli") == "shoes"


# ============================================================================
# 5. PARSE VISION RESPONSE TESTS
# ============================================================================

def test_parse_vision_response_price_range():
    # Price range: e.g. "29.9 - 39.9" on 1688 or Taobao
    sample = {
        "title": "Aesthetic Hoodie",
        "category": "卫衣",
        "raw_price": "29.9 - 39.9",
        "currency": "CNY",
        "sizes": ["S", "M", "L"],
        "colors": ["粉色"],
    }
    result = parse_vision_response(sample)
    assert result["success"] is True
    # 29.9 * 1800 = 53820 UZS (< 80000 -> 35% margin)
    assert result["source_price"] == 53820
    assert result["margin_percent"] == 35.0
    assert result["retail_price"] == 73000  # 53820 * 1.35 = 72657 -> 73000


def test_parse_vision_response_thousands_separator_uzs():
    # Uzbek som formatted with dots like "120.000 so'm"
    sample = {
        "title": "Koreyscha Ko'ylak",
        "category": "koylak",
        "raw_price": "120.000 so'm",
        "sizes": ["Standart"],
        "colors": ["Oq"],
    }
    result = parse_vision_response(sample)
    assert result["success"] is True
    assert result["source_price"] == 120000
    assert result["margin_percent"] == 30.0
    assert result["retail_price"] == 156000


def test_parse_vision_response_ruble_string():
    # Russian price without explicit currency key: "500 руб"
    sample = {
        "title": "Сумка женская",
        "category": "сумка",
        "raw_price": "500 руб",
        "colors": ["черный"],
    }
    result = parse_vision_response(sample)
    assert result["success"] is True
    assert result["currency"] == "RUB"
    assert result["source_price"] == 70000  # 500 * 140
    assert result["retail_price"] == 94000  # 70000 * 1.35 = 94500 -> 94000 (round half to even)
    # Because category is sumka and sizes was empty, it defaults to Standart
    assert result["sizes"] == ["Standart"]


def test_parse_vision_response_one_size_categories():
    # Bag, cosmetics, wigs default to Standart if no sizes were found
    sample = {
        "title": "Aesthetic Ayollar Sumkasi",
        "category": "sumka",
        "raw_price": 45.0,
        "currency": "CNY",
        "colors": ["Bej"],
    }
    result = parse_vision_response(sample)
    assert result["sizes"] == ["Standart"]


def test_parse_vision_response_chinese_pinduoduo():
    sample = {
        "title": "Vintage Pushti Hoodie 🌸",
        "category": "卫衣",
        "raw_price": 38.5,
        "currency": "CNY",
        "sizes": ["S-2XL"],
        "colors": ["粉色", "白色", "黑色"],
        "cargo_rate": 10000,
        "weight_grams": 450,
    }

    result = parse_vision_response(sample)
    assert result["success"] is True
    assert result["category"] == "hoodie"
    assert "Vintage Pushti Hoodie" in result["title"]
    # 38.5 * 1800 = 69300 UZS (< 80000 -> 35% margin)
    assert result["source_price"] == 69300
    assert result["margin_percent"] == 35.0
    assert result["retail_price"] == 94000  # 69300 * 1.35 = 93555 -> 94000
    assert result["sizes"] == ["S", "M", "L", "XL", "2XL"]
    assert result["colors"] == ["Pushti 🌸", "Oq 🤍", "Qora 🖤"]
    assert result["cargo_rate"] == 10000
    assert result["weight_grams"] == 450


def test_parse_vision_response_russian_marketplace():
    sample = {
        "title": "Элегантное белое платье",
        "category": "платье",
        "raw_price": "1 500 ₽",
        "sizes": ["Стандарт"],
        "colors": ["белый", "розовый"],
    }

    result = parse_vision_response(sample)
    assert result["success"] is True
    assert result["category"] == "koylak"
    # 1500 * 140 = 210,000 UZS (> 200,000 -> 25% margin)
    assert result["source_price"] == 210000
    assert result["margin_percent"] == 25.0
    assert result["retail_price"] == 262000
    assert result["sizes"] == ["Standart"]
    assert result["colors"] == ["Oq 🤍", "Pushti 🌸"]


def test_parse_vision_response_english_ecommerce():
    sample = {
        "title": "Korean Style Crossbody Bag",
        "category": "bag",
        "raw_price": 18.0,
        "currency": "USD",
        "sizes": ["One size"],
        "colors": ["Black", "Beige", "Light Blue"],
    }

    result = parse_vision_response(sample)
    assert result["success"] is True
    assert result["category"] == "sumka"
    # 18 * 12900 = 232,200 UZS (> 200,000 -> 25% margin)
    assert result["source_price"] == 232200
    assert result["margin_percent"] == 25.0
    assert result["retail_price"] == 290000  # 232200 * 1.25 = 290250 -> 290000
    assert result["sizes"] == ["Standart"]
    assert result["colors"] == ["Qora 🖤", "Bej 🤎", "Havorang 🩵"]


# ============================================================================
# 6. ASYNC EXTRACT_PRODUCT_FROM_IMAGE TESTS (WITH MOCK GEMINI API)
# ============================================================================

@pytest.mark.asyncio
async def test_extract_product_without_api_key():
    with patch("api.services.vision_ocr.settings.GEMINI_API_KEY", None), \
         patch.dict("os.environ", {}, clear=True):
        res = await extract_product_from_image(b"\xff\xd8\xff\xe0fake_jpeg", api_key="")
        assert res["success"] is False
        assert "GEMINI_API_KEY is not configured" in res["error"]


@pytest.mark.asyncio
async def test_extract_product_empty_image():
    res = await extract_product_from_image(b"", api_key="fake-key-123")
    assert res["success"] is False
    assert "Invalid or empty image data" in res["error"]


@pytest.mark.asyncio
async def test_extract_product_with_bytes_io():
    fake_gemini_response = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {
                            "text": json.dumps({
                                "title": "Pushti Yumshoq Hoodie",
                                "category": "hoodie",
                                "raw_price": 32.0,
                                "currency": "CNY",
                                "sizes": ["S", "M", "L"],
                                "colors": ["粉色"],
                            })
                        }
                    ]
                }
            }
        ]
    }

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = fake_gemini_response

    mock_client = AsyncMock()
    mock_client.post.return_value = mock_resp
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None

    with patch("httpx.AsyncClient", return_value=mock_client):
        bio = io.BytesIO(b"\xff\xd8\xff\xe0mock_data_for_bytes_io")
        res = await extract_product_from_image(bio, api_key="test-api-key")
        assert res["success"] is True
        assert res["title"] == "Pushti Yumshoq Hoodie"


@pytest.mark.asyncio
async def test_extract_product_success_mock_gemini():
    fake_gemini_response = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {
                            "text": "```json\n" + json.dumps({
                                "title": "Pushti Yumshoq Hoodie",
                                "category": "hoodie",
                                "raw_price": 32.0,
                                "currency": "CNY",
                                "sizes": ["S-2XL"],
                                "colors": ["粉色", "米色"],
                                "cargo_rate": 10000,
                            }) + "\n```"
                        }
                    ]
                }
            }
        ]
    }

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = fake_gemini_response

    mock_client = AsyncMock()
    mock_client.post.return_value = mock_resp
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None

    with patch("httpx.AsyncClient", return_value=mock_client):
        res = await extract_product_from_image(
            b"\xff\xd8\xff\xe0mock_data",
            api_key=" test-api-key ",  # test whitespace trimming
        )

        assert res["success"] is True
        assert res["category"] == "hoodie"
        assert res["title"] == "Pushti Yumshoq Hoodie"
        # 32 * 1800 = 57600 (< 80000 -> 35% margin)
        assert res["source_price"] == 57600
        assert res["retail_price"] == 78000  # 57600 * 1.35 = 77760 -> 78000
        assert res["sizes"] == ["S", "M", "L", "XL", "2XL"]
        assert res["colors"] == ["Pushti 🌸", "Bej 🤎"]


@pytest.mark.asyncio
async def test_extract_product_network_timeout():
    import httpx

    mock_client = AsyncMock()
    mock_client.post.side_effect = httpx.TimeoutException("Connection timed out")
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None

    with patch("httpx.AsyncClient", return_value=mock_client):
        res = await extract_product_from_image(
            b"\xff\xd8\xff\xe0mock_data",
            api_key="test-api-key",
        )

        assert res["success"] is False
        assert "timed out" in res["error"]
        assert res["source_price"] == 0


# ============================================================================
# 7. INTEGRATION TESTS WITH BOT PROCESS_PRODUCT_IMPORT
# ============================================================================

@pytest.mark.asyncio
async def test_bot_process_product_import_with_vision(test_db_session):
    """
    Simulates admin sending a screenshot (photo without caption) where
    AI Vision successfully extracts price, sizes, and colors, immediately
    showing the final product import summary card with '✅ To'g'ri, saqlash & kanalga joylash'.
    """
    from bot.handlers.admin import process_product_import
    from aiogram.fsm.storage.memory import MemoryStorage
    from aiogram.fsm.context import FSMContext
    from aiogram.fsm.storage.base import StorageKey

    storage = MemoryStorage()
    key = StorageKey(bot_id=1, chat_id=1234567, user_id=1234567)
    state = FSMContext(storage=storage, key=key)

    mock_message = MagicMock()
    mock_message.from_user = MagicMock()
    mock_message.from_user.id = 1234567
    mock_message.photo = [MagicMock(file_id="tg_photo_file_123")]
    mock_message.answer = AsyncMock()

    mock_bot = AsyncMock()
    mock_bot.download = AsyncMock(return_value=io.BytesIO(b"\xff\xd8\xff\xe0real_bytes"))
    mock_message.bot = mock_bot

    vision_mock_return = {
        "success": True,
        "title": "Aesthetic Vintage Hoodie 🌸",
        "category": "hoodie",
        "source_price": 54000,
        "retail_price": 73000,
        "price": 73000,
        "margin_percent": 35.0,
        "raw_price": 30.0,
        "currency": "CNY",
        "sizes": ["S", "M", "L", "XL", "2XL"],
        "colors": ["Pushti 🌸", "Oq 🤍"],
        "cargo_rate": 10000,
        "weight_grams": 400,
    }

    with patch("bot.handlers.admin.extract_product_from_image", AsyncMock(return_value=vision_mock_return)), \
         patch("bot.handlers.admin.show_product_import_summary", AsyncMock()) as mock_show_summary:

        await process_product_import(
            message=mock_message,
            state=state,
            raw_text="",
            photos=["tg_photo_file_123"],
            source_label="Sehrli import",
        )

        # State must have saved extracted vision data
        data = await state.get_data()
        assert data["price"] == 73000
        assert data["source_price"] == 54000
        assert data["sizes"] == ["S", "M", "L", "XL", "2XL"]
        assert data["colors"] == ["Pushti 🌸", "Oq 🤍"]
        assert data["category"] == "hoodie"
        # Description should not be empty, defaults to title
        assert data["description"] == "Aesthetic Vintage Hoodie 🌸"

        # Because price, sizes, and colors are all present, show_product_import_summary must be called directly!
        mock_show_summary.assert_called_once_with(mock_message, state)


@pytest.mark.asyncio
async def test_bot_process_product_import_vision_fallback_on_missing_key():
    """
    When Gemini API is not configured or fails, the handler gracefully
    falls back to the interactive step-by-step wizard (asking for price first).
    """
    from bot.handlers.admin import process_product_import, ProductWizard
    from aiogram.fsm.storage.memory import MemoryStorage
    from aiogram.fsm.context import FSMContext
    from aiogram.fsm.storage.base import StorageKey

    storage = MemoryStorage()
    key = StorageKey(bot_id=1, chat_id=1234567, user_id=1234567)
    state = FSMContext(storage=storage, key=key)

    mock_message = MagicMock()
    mock_message.from_user = MagicMock()
    mock_message.from_user.id = 1234567
    mock_message.photo = [MagicMock(file_id="tg_photo_file_fallback")]
    mock_message.answer = AsyncMock()

    mock_bot = AsyncMock()
    mock_bot.download = AsyncMock(return_value=io.BytesIO(b"\xff\xd8\xff\xe0fallback_bytes"))
    mock_message.bot = mock_bot

    failed_vision_return = {
        "success": False,
        "error": "GEMINI_API_KEY is not configured",
        "source_price": 0,
        "retail_price": 0,
        "price": 0,
        "sizes": [],
        "colors": [],
    }

    with patch("bot.handlers.admin.extract_product_from_image", AsyncMock(return_value=failed_vision_return)), \
         patch("bot.handlers.admin.show_product_import_summary", AsyncMock()) as mock_show_summary:

        await process_product_import(
            message=mock_message,
            state=state,
            raw_text="",
            photos=["tg_photo_file_fallback"],
            source_label="Sehrli import",
        )

        # Show summary should NOT be called because price is missing
        mock_show_summary.assert_not_called()
        # State must transition to ProductWizard.price for admin input
        cur_state = await state.get_state()
        assert cur_state == ProductWizard.price.state
        # Message should prompt for price
        prompt_text = mock_message.answer.call_args[0][0]
        assert "Mahsulot narxini kiriting" in prompt_text


@pytest.mark.asyncio
async def test_bot_boost_command_text_only():
    """
    Verifies /boost command output describes AI Multimodal Vision status and instructions.
    """
    from bot.handlers.admin import handle_boost_command

    mock_message = MagicMock()
    mock_message.photo = None
    mock_message.answer = AsyncMock()

    with patch("bot.handlers.admin.settings.GEMINI_API_KEY", "mock_key"):
        await handle_boost_command(mock_message)

        mock_message.answer.assert_called_once()
        text = mock_message.answer.call_args[0][0]
        assert "AI Multimodal Vision Boost faol" in text
        assert "1 ¥ = 1,800 so'm" in text
        assert "Pinduoduo, 1688, Taobao" in text


@pytest.mark.asyncio
async def test_bot_boost_command_with_photo(test_db_session):
    """
    Verifies that when an admin sends /boost with a photo (or a photo with caption /boost),
    it routes to product import and triggers the AI Vision pipeline rather than
    ignoring the photo.
    """
    from bot.handlers.admin import handle_boost_command
    from aiogram.fsm.storage.memory import MemoryStorage
    from aiogram.fsm.context import FSMContext
    from aiogram.fsm.storage.base import StorageKey

    storage = MemoryStorage()
    key = StorageKey(bot_id=1, chat_id=1234567, user_id=1234567)
    state = FSMContext(storage=storage, key=key)

    mock_message = MagicMock()
    mock_message.from_user = MagicMock()
    mock_message.from_user.id = 1234567
    mock_message.media_group_id = None
    mock_message.forward_origin = None
    mock_message.forward_from_chat = None
    mock_message.forward_date = None
    mock_photo = MagicMock()
    mock_photo.file_id = "boost_photo_id_777"
    mock_message.photo = [mock_photo]
    mock_message.caption = "/boost"
    mock_message.text = None
    mock_message.answer = AsyncMock()

    mock_bot = AsyncMock()
    mock_bot.download = AsyncMock(return_value=io.BytesIO(b"\xff\xd8\xff\xe0mock_boost_image"))
    mock_message.bot = mock_bot

    vision_mock_return = {
        "success": True,
        "title": "Korean Style Aesthetic Jempir 🌸",
        "category": "jempir",
        "source_price": 54000,
        "retail_price": 73000,
        "price": 73000,
        "margin_percent": 35.0,
        "raw_price": 30.0,
        "currency": "CNY",
        "sizes": ["Standart"],
        "colors": ["Pushti 🌸"],
        "cargo_rate": 10000,
        "weight_grams": 350,
    }

    with patch("bot.handlers.admin.extract_product_from_image", AsyncMock(return_value=vision_mock_return)), \
         patch("bot.handlers.admin.show_product_import_summary", AsyncMock()) as mock_show_summary, \
         patch("bot.handlers.admin.is_user_admin", AsyncMock(return_value=True)):

        await handle_boost_command(mock_message, state=state)

        # Must have routed to import and called show_product_import_summary
        mock_show_summary.assert_called_once_with(mock_message, state)
        data = await state.get_data()
        assert data["price"] == 73000
        assert data["category"] == "jempir"
        assert data["sizes"] == ["Standart"]
        assert data["source_label"] == "AI Vision Boost 🚀"
        # Description must NOT be "/boost"
        assert data["description"] != "/boost"
