import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from api.config import settings
from api.services.vision_ocr import (
    DEFAULT_GEMINI_MODEL,
    GEMINI_FALLBACK_CASCADE,
    extract_product_from_image,
)
from api.services.gemini_assistant import (
    ask_gemini,
    parse_product_text_with_ai,
    answer_customer_support_query,
)


def test_gemini_38_flash_is_primary_model():
    """Verify Gemini 3.8 Flash is set as primary across config and cascade."""
    assert settings.GEMINI_VISION_MODEL == "gemini-3.8-flash"
    assert DEFAULT_GEMINI_MODEL == "gemini-3.8-flash"
    assert GEMINI_FALLBACK_CASCADE[0] == "gemini-3.8-flash"
    assert "gemini-3.6-flash" in GEMINI_FALLBACK_CASCADE
    assert "gemini-3.5-flash" in GEMINI_FALLBACK_CASCADE
    assert "gemini-3.1-flash-lite" in GEMINI_FALLBACK_CASCADE


@pytest.mark.asyncio
async def test_ask_gemini_mocked_success():
    """Verify ask_gemini handles prompt and returns structured response."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "candidates": [
            {
                "content": {
                    "parts": [{"text": "Test response from Gemini 3.8 Flash"}]
                }
            }
        ]
    }

    mock_client = AsyncMock()
    mock_client.post.return_value = mock_resp
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None

    with patch("httpx.AsyncClient", return_value=mock_client):
        res = await ask_gemini("Test prompt", model="gemini-3.8-flash")
        assert res["success"] is True
        assert res["text"] == "Test response from Gemini 3.8 Flash"
        assert res["model_used"] == "gemini-3.8-flash"


@pytest.mark.asyncio
async def test_parse_product_text_with_ai_mocked():
    """Verify parse_product_text_with_ai correctly extracts and formats product data."""
    mock_json_text = """{
        "title": "Aesthetic Vintage Pushti Kardigan",
        "category": "jempir",
        "raw_price": 45,
        "currency": "CNY",
        "sizes": ["S", "M", "L", "XL"],
        "colors": ["Pushti 🌸", "Oq 🤍"],
        "description": "Yumshoq koreyscha kardigan."
    }"""

    with patch("api.services.gemini_assistant.ask_gemini", new_callable=AsyncMock) as mock_ask:
        mock_ask.return_value = {
            "success": True,
            "text": mock_json_text,
            "model_used": "gemini-3.8-flash",
        }

        res = await parse_product_text_with_ai("Pushti kardigan 45 yuan...")
        assert res["success"] is True
        assert res["title"] == "Aesthetic Vintage Pushti Kardigan"
        assert res["category"] == "jempir"
        assert res["source_price"] == 45 * 1800  # 81000
        assert res["retail_price"] == 105000  # 81000 * 1.30 = 105300 -> rounded to 105000
        assert res["sizes"] == ["S", "M", "L", "XL"]
        assert "Pushti 🌸" in res["colors"]


@pytest.mark.asyncio
async def test_customer_support_query_reply():
    """Verify customer support query replies with polite aesthetic text."""
    with patch("api.services.gemini_assistant.ask_gemini", new_callable=AsyncMock) as mock_ask:
        mock_ask.return_value = {
            "success": True,
            "text": "Assalomu alaykum! 🌸 Yetkazib berish 7-18 kun davom etadi.",
            "model_used": "gemini-3.8-flash",
        }

        reply = await answer_customer_support_query("Yetkazib berish qancha vaqt oladi?")
        assert "Assalomu alaykum" in reply
        assert "7-18 kun" in reply
