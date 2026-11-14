import json
import logging
import re
from typing import Any, Dict, List, Optional

import httpx

from api.config import settings
from api.services.formatters import calculate_retail_price, calculate_margin_percent
from api.services.vision_ocr import (
    GEMINI_FALLBACK_CASCADE,
    GEMINI_ENDPOINT_TEMPLATE,
    convert_currency_to_uzs,
    normalize_category,
    normalize_colors,
    normalize_sizes,
)

logger = logging.getLogger("moonlight_gemini_assistant")

SHOP_SYSTEM_PROMPT = (
    "Siz 'Moonlight Chinese Shop' do'konining aqlli, muloyim va estetik AI maslahatchisisiz 🌸✨.\n"
    "Do'kon faoliyati: Xitoy va Janubiy Koreya brendlari, aesthetic kiyimlar, sumkalar, pariklar, "
    "aksessuarlar va go'zallik mahsulotlarini O'zbekiston bo'ylab buyurtma asosida yetkazib beradi.\n"
    "Qoidalar:\n"
    "- Faqat toza, xushmuomala o'zbek tilida (lotin alifbosida) javob bering.\n"
    "- Aesthetic emoji-lardan (🌸, 🎀, 🌙, ✨, 🤍, 🛍) me'yorida foydalaning.\n"
    "- Mijozga har doim yordam berishga tayyor ekanligingizni bildiring.\n"
    "- Yetkazib berish muddati: 7-18 kun (avto: 14-18 kun, avia: 7-9 kun).\n"
    "- Kargo narxi: 100 gramm uchun taxminan 10.000 - 12.000 so'm.\n"
    "- Buyurtma berish: Mini App orqali yoki admin @MOONLIGHT_ADMINNN orqali qabul qilinadi.\n"
)


async def ask_gemini(
    prompt: str,
    system_instruction: Optional[str] = None,
    model: Optional[str] = None,
    temperature: float = 0.2,
    thinking_budget: int = 1024,
    response_mime_type: Optional[str] = None,
    timeout: float = 25.0,
) -> Dict[str, Any]:
    """
    Universal call to Google Gemini with Gemini 3.8 Flash High as primary
    and resilient fallback cascade.
    """
    raw_key = getattr(settings, "GEMINI_API_KEY", None)
    resolved_key = raw_key.strip().strip("'\"") if raw_key else None
    if not resolved_key:
        return {"success": False, "error": "GEMINI_API_KEY is not configured", "text": "", "model_used": None}

    primary = model or getattr(settings, "GEMINI_VISION_MODEL", "gemini-3.8-flash")
    models_to_try = [primary]
    for m in GEMINI_FALLBACK_CASCADE:
        if m not in models_to_try:
            models_to_try.append(m)

    contents: List[Dict[str, Any]] = []
    if system_instruction:
        contents.append({"role": "user", "parts": [{"text": f"System Context:\n{system_instruction}\n\nTask:\n{prompt}"}]})
    else:
        contents.append({"parts": [{"text": prompt}]})

    base_payload: Dict[str, Any] = {"contents": contents}

    async with httpx.AsyncClient(timeout=timeout) as client:
        last_error = None
        for target_model in models_to_try:
            url = f"{GEMINI_ENDPOINT_TEMPLATE.format(model=target_model)}?key={resolved_key}"

            # Try first with thinkingConfig, fallback without it if rejected
            configs_to_try = [
                {
                    "temperature": temperature,
                    **({"response_mime_type": response_mime_type} if response_mime_type else {}),
                    "thinkingConfig": {"thinkingBudget": thinking_budget},
                },
                {
                    "temperature": temperature,
                    **({"response_mime_type": response_mime_type} if response_mime_type else {}),
                },
            ]

            for gen_config in configs_to_try:
                payload = {**base_payload, "generationConfig": gen_config}
                try:
                    resp = await client.post(url, json=payload)
                    if resp.status_code == 200:
                        data = resp.json()
                        candidates = data.get("candidates", [])
                        if not candidates:
                            last_error = f"{target_model} returned empty candidates"
                            break
                        parts = candidates[0].get("content", {}).get("parts", [])
                        if not parts:
                            last_error = f"{target_model} returned empty parts"
                            break
                        text = parts[0].get("text", "").strip()
                        return {
                            "success": True,
                            "text": text,
                            "model_used": target_model,
                            "raw": data,
                        }
                    elif resp.status_code == 400 and "thinkingConfig" in resp.text:
                        continue  # retry without thinkingConfig
                    else:
                        last_error = f"{target_model} returned {resp.status_code}: {resp.text[:150]}"
                        logger.warning(f"Gemini call error: {last_error}")
                        break
                except httpx.TimeoutException:
                    last_error = f"{target_model} timed out"
                    logger.warning(last_error)
                    break
                except Exception as e:
                    last_error = f"{target_model} exception: {e}"
                    logger.warning(last_error)
                    break

        return {"success": False, "error": last_error or "All models failed", "text": "", "model_used": None}


async def parse_product_text_with_ai(raw_text: str) -> Dict[str, Any]:
    """
    Intelligently extracts product specifications (title, price, sizes, colors, category)
    from text or forwarded message in Uzbek, Russian, Chinese, or English.
    """
    prompt = (
        "You are an expert e-commerce product extraction AI for 'Moonlight Chinese Shop'.\n"
        "Extract product details from the following message/caption:\n"
        f"'''\n{raw_text}\n'''\n\n"
        "Rules:\n"
        "1. title: Aesthetic product title in Uzbek Latin (e.g. 'Vintage Pushti Jempir', 'Koreyscha Belbog'li Kurtka').\n"
        "2. category: Strictly one of ['hoodie', 'koylak', 'yubka', 'sumka', 'shoes', 'jempir', 'shim', 'futbolka', 'kurtka', 'palto', 'wig', 'scarf', 'aksessuar', 'kosmetika', 'soat', 'dekor'].\n"
        "3. raw_price: Numeric price found (e.g. 29.9 or 95000).\n"
        "4. currency: Currency code ('CNY', 'USD', 'RUB', or 'UZS').\n"
        "5. sizes: Array of sizes (e.g. ['S', 'M', 'L'] or ['Standart']). For bags/accessories/cosmetics default to ['Standart'].\n"
        "6. colors: Array of colors in aesthetic Uzbek with emojis (e.g. ['Pushti 🌸', 'Oq 🤍']).\n"
        "7. description: Clean, appealing description in Uzbek (2-3 sentences).\n\n"
        "Output ONLY a JSON object:\n"
        "{\n"
        '  "title": "string",\n'
        '  "category": "string",\n'
        '  "raw_price": 0.0,\n'
        '  "currency": "CNY",\n'
        '  "sizes": ["string"],\n'
        '  "colors": ["string"],\n'
        '  "description": "string"\n'
        "}"
    )

    res = await ask_gemini(prompt, response_mime_type="application/json")
    if not res.get("success") or not res.get("text"):
        return {"success": False, "error": res.get("error", "AI parsing failed")}

    try:
        raw_output = res["text"]
        m_json = re.search(r"\{.*\}", raw_output, re.DOTALL)
        json_str = m_json.group(0) if m_json else raw_output
        data = json.loads(json_str)

        title = str(data.get("title", "")).strip() or "Yangi Mahsulot 🌸"
        category = normalize_category(data.get("category"))
        raw_price = float(data.get("raw_price", 0.0) or 0.0)
        currency = str(data.get("currency", "CNY")).upper()
        sizes = normalize_sizes(data.get("sizes"))
        colors = normalize_colors(data.get("colors"))
        description = str(data.get("description", "")).strip()

        # Currency conversion & profit margin
        yuan_rate = getattr(settings, "YUAN_TO_UZS_RATE", 1800)
        source_price = convert_currency_to_uzs(raw_price, currency, yuan_rate=yuan_rate)
        margin_percent = calculate_margin_percent(source_price)
        retail_price = calculate_retail_price(source_price, margin_percent)

        return {
            "success": True,
            "title": title,
            "category": category,
            "raw_price": raw_price,
            "currency": currency,
            "source_price": source_price,
            "retail_price": retail_price,
            "margin_percent": margin_percent,
            "sizes": sizes,
            "colors": colors,
            "description": description,
            "model_used": res.get("model_used"),
        }
    except Exception as e:
        logger.error(f"Failed to parse AI JSON response: {e}")
        return {"success": False, "error": str(e)}


async def answer_customer_support_query(user_message: str, current_products_summary: Optional[str] = None) -> str:
    """
    Answers a customer's message politely using Gemini 3.8 Flash High.
    """
    context = SHOP_SYSTEM_PROMPT
    if current_products_summary:
        context += f"\n\nDo'kondagi mavjud tovarlar ro'yxati:\n{current_products_summary}\n"

    prompt = (
        f"Mijoz quyidagi xabarni yozdi:\n"
        f"'''\n{user_message}\n'''\n\n"
        "Mijozga do'konimiz nomidan muloyim, qisqa va aniq javob bering. "
        "Agar tovarlar haqida so'rasa, Mini App orqali to'liq ko'rish mumkinligini yoki admin @MOONLIGHT_ADMINNN ga yozishini eslatib o'ting."
    )

    res = await ask_gemini(prompt, system_instruction=context, temperature=0.3)
    if res.get("success") and res.get("text"):
        return res["text"]

    return (
        "Assalomu alaykum! 🌸 Moonlight Chinese Shop ga xush kelibsiz ✨\n\n"
        "Sizga qanday yordam bera olamiz? Barcha go'zal tovarlarimizni quyidagi "
        "<b>'🛍 Do'kon'</b> tugmasi orqali Mini Appda ko'rishingiz va buyurtma berishingiz mumkin 🎀\n\n"
        "Savollaringiz bo'lsa, adminga ham yozishingiz mumkin: @MOONLIGHT_ADMINNN 💌"
    )
