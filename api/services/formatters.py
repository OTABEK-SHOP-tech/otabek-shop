import math
import re
from html import escape
from typing import Optional, List, Dict, Any


def format_price(price: int) -> str:
    """
    Format integer price with dot as thousands separator plus 'so'm'.
    Example: 99000 -> '99.000 so\'m'
             1250000 -> '1.250.000 so\'m'
             0 -> '0 so\'m'
    """
    if price is None:
        return "0 so'm"
    formatted = f"{int(price):,}".replace(",", ".")
    return f"{formatted} so'm"


def strip_private_pricing_data(text: Optional[str]) -> str:
    """
    Strips supplier / original prices, profit percentages, and internal margin notes
    from text to strictly guarantee customer and public channel privacy.
    Ensures that customer-facing texts and channel posts only show the clean retail price.

    Examples of stripped patterns:
    - '+35% foyda', '35% foyda', '+30%', '+35%', 'foyda: 35%', 'foyda marjasi: 30%'
    - 'Foyda: 20.000 so\'m', '20.000 so\'m foyda', 'Sof foyda: 25.000 so\'m', 'Ustama: 20.000 so\'m'
    - 'Asl narxi (ta\'minotchi): 50.000 so\'m', 'Asl narxi: 50.000', 'Asl narhi: 50.000'
    - 'Tannarx: 45.000', 'Tan narhi: 45000', 'Optom narx: 40000', 'optom 40k', 'optom 40 ming'
    - 'Оптом 50000 сум', 'Опт: 50000 сум', 'Себестоимость: 3000', 'Закупка: 4500 руб', 'Закуп: 5000'
    - '进货价: 35元', '成本: 35元', '批发价: 40'

    NEVER strips harmless percentages like:
    - '100% paxta', '95% paxta, 5% elastan', '100% original', '100% sifatli'
    """
    if not text:
        return ""
    s = str(text)
    orig_lines = s.split("\n")

    # Currency suffix pattern
    curr = r"(?:so['’`]?m|som|сум|rub|руб|usd|dollar|доллар|yuan|rmb|юань|[¥￥$€元块])?"
    # Price number pattern e.g. 50.000, 50 000, 50000, 50k, 50 ming
    num = r"(?:\d{1,3}(?:[.\s]\d{3})+|\d+(?:[.,]\d+)?)\s*(?:k|ming)?"

    # 1. Supplier / cost / wholesale price lines or phrases
    supplier_pattern = (
        r"(?i)(?:📥\s*)?(?:"
        r"asl\s*nar[xh](?:i)?|"
        r"ta['’`]?minotchi(?:\s*nar[xh](?:i)?)?|"
        r"tan\s*nar[xh](?:i)?|tannar[xh](?:i)?|"
        r"optom(?:\s*nar[xh](?:i)?)?|"
        r"opt\b(?:\s*nar[xh](?:i)?|:)?|"
        r"опт(?:ом)?\b(?:\s*цена|:)?|"
        r"ulgurji(?:\s*nar[xh](?:i)?)?|"
        r"исходная\s*цена|себестоимость|закупочная\s*цена|закупка|закуп\b|оптовая\s*цена|цена\s*поставщика|"
        r"cost\s*price|source\s*price|supplier(?:\s*price)?|wholesale(?:\s*price)?|"
        r"成本(?:价)?|进货价|进价|批发价|原价|拿货价"
        r")"
        r"(?:\s*\([^)]*\))?"
        r"\s*[:\-–—=]?\s*"
        rf"(?:[$¥￥€]\s*)?(?:{num})?\s*{curr}"
    )
    s = re.sub(supplier_pattern, "", s)

    # 2. Profit margin / markup expressions (percentages or sum amounts)
    profit_keywords = r"(?:sof\s*)?(?:foyda(?:si)?|marja(?:si)?|ustama|marzh|profit|прибыль|маржа|наценка)"

    # 2a. Prefix keyword with percentage or sum amount: e.g. "Foyda: 35%", "Foyda: 20.000 so'm", "foyda marjasi: 30%"
    profit_prefix = (
        rf"(?i)(?:📈\s*)?{profit_keywords}(?:\s*marjasi)?"
        rf"\s*[:\-–—=]?\s*(?:\+\s*)?(?:{num}\s*%?|(?:\d+(?:\.\d+)?%))\s*{curr}"
    )
    s = re.sub(profit_prefix, "", s)

    # 2b. Suffix keyword with percentage or sum amount: e.g. "35% foyda", "20.000 so'm foyda", "35% ustama"
    profit_suffix = (
        rf"(?i)(?:📈\s*)?(?:(?:\+\s*)?{num}\s*%?|\d+(?:\.\d+)?%)\s*{curr}\s*{profit_keywords}"
    )
    s = re.sub(profit_suffix, "", s)

    # 2c. Pure markup with plus sign: e.g. "+35%", "+ 35%", "+30.5%"
    profit_pure_plus = r"(?i)(?:📈\s*)?\+\s*\d+(?:\.\d+)?%"
    s = re.sub(profit_pure_plus, "", s)

    # 3. Clean up empty parentheses, brackets, or dangling punctuation left over
    s = re.sub(r"\(\s*[,;\s\-–—|/]*\)", "", s)
    s = re.sub(r"\[\s*[,;\s\-–—|/]*\]", "", s)
    s = re.sub(r"\{\s*[,;\s\-–—|/]*\}", "", s)

    lines_after = s.split("\n")
    cleaned_lines = []
    for orig, line in zip(orig_lines, lines_after):
        orig_s = orig.strip()
        cl = re.sub(r"[ \t]+", " ", line).strip()
        cl = re.sub(r"^\s*[:\-–—|/,;]\s*", "", cl).strip()
        cl = re.sub(r"\s*[:\-–—|/,;]\s*$", "", cl).strip()
        if orig_s and not cl:
            continue
        cleaned_lines.append(cl)

    res = "\n".join(cleaned_lines)
    res = re.sub(r"\n{3,}", "\n\n", res)
    return res.strip()


CARGO_STAGE_NAMES = {
    "china_warehouse": "🇨🇳 Xitoy omborida",
    "in_transit_border": "🚛 Xorgos chegarasida",
    "customs_clearance": "🛃 Bojxona nazoratida",
    "tashkent_hub": "📍 Toshkent omborida",
    "delivering": "🛍 Yetkazilmoqda",
}


def format_cargo_stage(stage: Optional[str]) -> str:
    return CARGO_STAGE_NAMES.get(stage or "china_warehouse", "🇨🇳 Xitoy omborida")


def mask_user_id(user_id: Optional[int]) -> str:
    if not user_id:
        return "ID: ***"
    s = str(user_id)
    if len(s) <= 4:
        return s[:1] + "***" + s[-1:]
    return s[:4] + "***" + s[-3:]


def mask_customer_name(name: Optional[str]) -> str:
    clean = (name or "Mijoz").strip()
    if len(clean) <= 2:
        return clean[0] + "***" if len(clean) >= 1 else "M***"
    return clean[0] + "*" * min(5, len(clean) - 2) + clean[-1]


NON_CLOTHING_CATEGORIES = {
    "sumka", "aksessuar", "kosmetika", "wig", "scarf", "soat", "dekor",
}


def is_non_clothing_category(cat: Optional[str]) -> bool:
    if not cat:
        return False
    return cat.lower().replace("#", "").strip() in NON_CLOTHING_CATEGORIES


STANDARD_SIZES = ["XXS", "XS", "S", "M", "L", "XL", "2XL", "3XL", "4XL", "5XL"]
SIZE_ALIASES = {
    "XXL": "2XL",
    "XXXL": "3XL",
    "XXXXL": "4XL",
    "2X": "2XL",
    "3X": "3XL",
    "4X": "4XL",
}

CYRILLIC_TO_LATIN_CATEGORY = {
    "худи": "hoodie",
    "толстовка": "hoodie",
    "hudi": "hoodie",
    "парик": "wig",
    "парики": "wig",
    "свитер": "jempir",
    "джемпер": "jempir",
    "кофта": "jempir",
    "шарф": "scarf",
    "шарфы": "scarf",
    "сумка": "sumka",
    "сумки": "sumka",
    "платье": "koylak",
    "юбка": "yubka",
    "обувь": "shoes",
    "кроссовки": "shoes",
    "туфли": "shoes",
    "аксессуар": "aksessuar",
    "аксессуары": "aksessuar",
    "бижутерия": "aksessuar",
    "косметика": "kosmetika",
    "помада": "kosmetika",
    "духи": "kosmetika",
    "парфюм": "kosmetika",
    "крем": "kosmetika",
    "часы": "soat",
    "декор": "dekor",
    "игрушка": "dekor",
    "игрушки": "dekor",
    "штаны": "shim",
    "брюки": "shim",
    "джинсы": "shim",
    "футболка": "futbolka",
    "куртка": "kurtka",
    "пальто": "palto",
}

STOP_WORDS_SIZE = {
    "mavjud", "bor", "gacha", "dan", "razmer", "razmerlar", "razmeri", "o'lcham", "o'lchamlari",
    "o`lcham", "o`lchamlari", "o’lcham", "o’lchamlari", "размер", "размеры", "в", "наличии",
    "до", "от", "ta", "dona", "штук", "shtuk", "mavjut", "bitta", "bir", "o'lchamda",
}


def normalize_size_token(token: str) -> str:
    cleaned = re.sub(r"[^\w\-]", "", token).strip().upper()
    return SIZE_ALIASES.get(cleaned, cleaned)


def parse_sizes(raw_sizes: str) -> List[str]:
    """
    Parse size string into list of standard sizes.
    Supports:
    - 'S-2XL' or 'S - 2XL' -> ['S', 'M', 'L', 'XL', '2XL']
    - 'S-XXL' -> ['S', 'M', 'L', 'XL', '2XL']
    - '36-40' or '36 dan 40 gacha' -> ['36', '37', '38', '39', '40']
    - 'S, M, L' or 'S/M/L' -> ['S', 'M', 'L']
    - 'Standart' / 'Free size' -> ['Standart']
    - 'Razmer: S-2XL mavjud 🌸' -> ['S', 'M', 'L', 'XL', '2XL']
    - 'Razmer: S-2XL (oversize)' -> ['S', 'M', 'L', 'XL', '2XL']
    """
    if not raw_sizes:
        return []
    clean = raw_sizes.strip()

    # 1. Strip common prefixes like 'Razmer:', 'O'lcham:', '👗', etc.
    clean = re.sub(
        r"^(?:👗\s*)?(?:razmer(?:lar|i)?|o['’`]?lcham(?:lar|i)?|размер(?:ы)?|size(?:s)?)\s*[:\-]?\s*",
        "",
        clean,
        flags=re.IGNORECASE,
    ).strip()
    if not clean:
        return []

    # 1a. Strip bracketed weight / recommendation notes (e.g. "【建议90-105斤】", "(80-120斤)", "【80-95斤】")
    # so they are never mistakenly matched as shoe/numeric size ranges
    clean = re.sub(
        r"[（(【\[][^）)】\]]*(?:斤|kg|建议|适合|вес|weight|recom)[^）)】\]]*[）)】\]]",
        "",
        clean,
        flags=re.IGNORECASE,
    ).strip()
    if not clean:
        return []

    # 2. Check for keyword sizes (e.g. Standart, Free size, Oversize)
    lower_clean = clean.lower()
    if any(k in lower_clean for k in ("standart", "standard", "free size", "freesize", "bir o'lcham", "bitta o'lcham", "oversize")):
        if not re.search(r"\b(?:[SMLX]|2XL|3XL|\d{2})\s*[-–—~]\s*(?:[SMLX]|2XL|3XL|\d{2})\b", clean, re.IGNORECASE):
            if "free" in lower_clean:
                return ["Free size"]
            return ["Standart"]

    # 3. Check for letter size range e.g. "S-2XL", "S - 2XL", "S-XL", "M-3XL", "S-XXL", "S dan 2XL gacha"
    m_letter_range = re.search(
        r"\b([A-Za-z0-9]+)\s*(?:[-–—~]|dan)\s*([A-Za-z0-9]+)(?:\s*gacha)?\b",
        clean,
        re.IGNORECASE,
    )
    if m_letter_range:
        start_raw = normalize_size_token(m_letter_range.group(1))
        end_raw = normalize_size_token(m_letter_range.group(2))
        if start_raw in STANDARD_SIZES and end_raw in STANDARD_SIZES:
            s_idx = STANDARD_SIZES.index(start_raw)
            e_idx = STANDARD_SIZES.index(end_raw)
            if s_idx <= e_idx:
                return STANDARD_SIZES[s_idx : e_idx + 1]

    # 4. Check for numeric shoe/dress range e.g. "36-40", "36 dan 40 gacha", "35 - 41"
    m_num_range = re.search(
        r"\b(\d{2})\s*(?:[-–—~]|dan)\s*(\d{2})(?:\s*gacha)?\b",
        clean,
        re.IGNORECASE,
    )
    if m_num_range:
        s_num = int(m_num_range.group(1))
        e_num = int(m_num_range.group(2))
        if s_num <= e_num and (e_num - s_num) <= 20:
            return [str(n) for n in range(s_num, e_num + 1)]

    # 5. Fallback: tokenize by delimiters (comma, slash, space, semicolon, etc.)
    # Strip emojis and noise punctuation
    clean_no_emojis = re.sub(r"[^\w\s,;/|\-–—]", " ", clean)
    tokens = re.split(r"[,;/|\s]+", clean_no_emojis)
    result = []
    for t in tokens:
        t_clean = t.strip()
        if not t_clean or t_clean.lower() in STOP_WORDS_SIZE:
            continue
        norm = normalize_size_token(t_clean)
        if norm in STANDARD_SIZES or (norm.isdigit() and 10 <= int(norm) <= 60):
            if norm not in result:
                result.append(norm)
        elif norm in ("STANDART", "FREE SIZE", "OVERSIZE"):
            if "Standart" not in result:
                result.append("Standart")

    return result


def format_sizes_display(sizes: Optional[List[str]], enumerate_all: bool = False) -> str:
    """
    Format list of sizes for display.
    - When 1 to 4 sizes: always enumerates them all (e.g. ['S', 'M', 'L', 'XL'] -> 'S, M, L, XL')
      so customers clearly see every individual size rather than mistaking a range for only 2 sizes.
    - When 5 or more continuous sizes and enumerate_all=False: formats as 'S-2XL' or '36-40'.
    - If enumerate_all=True: always enumerates all sizes.
    """
    if not sizes:
        return ""
    clean_sizes = [str(s).strip() for s in sizes if s and str(s).strip()]
    if not clean_sizes:
        return ""

    if not enumerate_all:
        # Standard letter sizes: compress to Start-End ONLY if 5 or more continuous sizes (e.g. S-2XL)
        if len(clean_sizes) >= 5 and all(s in STANDARD_SIZES for s in clean_sizes):
            indices = [STANDARD_SIZES.index(s) for s in clean_sizes]
            if indices == list(range(indices[0], indices[-1] + 1)):
                return f"{clean_sizes[0]}-{clean_sizes[-1]}"

        # Numeric shoes/clothing range: compress ONLY if 5 or more continuous sizes (e.g. 36-40)
        if len(clean_sizes) >= 5 and all(s.isdigit() for s in clean_sizes):
            nums = [int(s) for s in clean_sizes]
            if nums == list(range(nums[0], nums[-1] + 1)):
                return f"{clean_sizes[0]}-{clean_sizes[-1]}"

    return ", ".join(clean_sizes)


def calculate_margin_percent(source_price: int) -> float:
    """
    Tier-based profit margin bounded strictly between 25% (min) and 35% (max):
    - Cheaper items (< 80.000 so'm): 35.0% (maximal margin)
    - Mid-range items (80.000 - 200.000 so'm, e.g. 95.000): 30.0%
    - Higher-value items (> 200.000 so'm): 25.0% (minimal margin)
    """
    if source_price <= 0:
        return 30.0
    if source_price < 80000:
        return 35.0
    elif source_price <= 200000:
        return 30.0
    else:
        return 25.0


def calculate_retail_price(
    source_price: int,
    margin_percent: Optional[float] = None,
    clamp: bool = True,
) -> int:
    """
    Adds profit margin to source price and rounds to clean 1,000 so'm.
    Example: 95.000 + 30% = 123.500 -> 124.000 so'm.
    If clamp=True, clamps margin between 25% and 35%.
    If clamp=False, allows any custom margin (e.g. 5% to 100%).
    """
    if not source_price or source_price <= 0:
        return 0
    if margin_percent is None:
        margin_percent = calculate_margin_percent(source_price)
    elif clamp:
        margin_percent = max(25.0, min(35.0, float(margin_percent)))
    else:
        margin_percent = float(margin_percent)
    raw_retail = source_price * (1.0 + margin_percent / 100.0)
    # Round to nearest clean 1,000 so'm
    return int(round(raw_retail / 1000.0) * 1000)


def calculate_cargo(weight_grams: Optional[int], rate_per_100g: int = 12000) -> int:
    """
    Calculate cargo estimate from weight: ceil(weight / 100) * rate_per_100g.
    Example: 350g -> ceil(3.5) = 4 -> 4 * 12000 = 48.000 so'm
             180g -> ceil(1.8) = 2 -> 2 * 12000 = 24.000 so'm
             None or 0 -> 0 so'm
    """
    if not weight_grams or weight_grams <= 0:
        return 0
    hundred_gram_units = math.ceil(weight_grams / 100.0)
    return hundred_gram_units * rate_per_100g


def _parse_price_token(token: str, yuan_rate: int = 1800) -> int:
    """Helper to convert price token like '95.000', '95 000', '95k', '95ming', '35 yuan', '¥35', '95000' to int."""
    if not token:
        return 0
    clean = token.lower().strip()

    # Check for Chinese Yuan / RMB (e.g. '35 yuan', '35 rmb', '¥35', '35元', '35 юань')
    m_yuan = re.search(r"(?:[¥￥]\s*(\d+(?:[.,]\d+)?)|(\d+(?:[.,]\d+)?)\s*(?:yuan|юань|rmb|cny|[元块]))", clean)
    if m_yuan:
        try:
            val_str = m_yuan.group(1) or m_yuan.group(2)
            yuan_val = float(val_str.replace(",", "."))
            return int(round(yuan_val * yuan_rate))
        except ValueError:
            pass

    m_k = re.match(r"^(\d+(?:[.,]\d+)?)\s*k$", clean)
    if m_k:
        try:
            return int(float(m_k.group(1).replace(",", ".")) * 1000)
        except ValueError:
            pass
    m_ming = re.match(r"^(\d+(?:[.,]\d+)?)\s*ming$", clean)
    if m_ming:
        try:
            return int(float(m_ming.group(1).replace(",", ".")) * 1000)
        except ValueError:
            pass
    digits = re.sub(r"\D", "", clean)
    if digits:
        try:
            return int(digits)
        except ValueError:
            pass
    return 0


def calculate_cargo_rate_with_profit(
    base_usd_per_kg: float,
    profit_uzs_per_100g: int = 2000,
    usd_rate: int = 12900,
    round_to_thousand: bool = True,
) -> int:
    """
    Calculate customer cargo rate per 100g from base USD/kg tariff + our profit per 100g.
    e.g. AVTO: base $5.88/kg -> 0.588*12900 = 7585 + 2000 = 9585 -> 10000 so'm / 100g
    e.g. AVIA: base $8.99/kg -> 0.899*12900 = 11597 + 2000 = 13597 -> 14000 so'm / 100g
    """
    cost_per_100g = (base_usd_per_kg / 10.0) * usd_rate
    customer_price = cost_per_100g + profit_uzs_per_100g
    if round_to_thousand:
        return math.ceil(customer_price / 1000) * 1000
    return math.ceil(customer_price / 100) * 100


def build_channel_caption(
    category_slug: str,
    price: int,
    cargo_rate: int = 10000,
    cargo_rate_avia: Optional[int] = None,
    cargo_rate_avto: Optional[int] = None,
    delivery_days: str = "7–18 kun",
    delivery_days_avia: str = "7–9 kun",
    delivery_days_avto: str = "14–18 kun",
    delivery_scope: str = "O'zbekiston bo'ylab",
    contact_username: str = "MOONLIGHT_ADMINNN",
    title: Optional[str] = None,
    sizes: Optional[List[str]] = None,
    colors: Optional[List[str]] = None,
    reviews_channel: Optional[str] = None,
    cargo_separate: bool = False,
    adapted_style: bool = False,
    webapp_url: Optional[str] = None,
    source_price: Optional[int] = None,
    margin_percent: Optional[float] = None,
    **kwargs: Any,
) -> str:
    """
    Build channel post caption.
    Supports both legacy format (for backward compatibility) and
    adapted Moonlight brand format with sizes, reviews channel, and separate cargo.
    When cargo_rate_avia & cargo_rate_avto are provided, it presents both AVIA and AVTO tariffs.

    PRIVACY GUARANTEE:
    Supplier prices ("Asl narxi") and profit margins ("+35% foyda") are NEVER shown
    in customer-facing channel captions. Only the clean retail price is displayed.
    """
    clean_cat = strip_private_pricing_data(category_slug).replace("#", "").strip()
    tag_line = f"#{clean_cat} 🌸"

    clean_title = ""
    if title:
        # Strip leading & trailing decorative flowers/sparkles/hashes
        clean_title = re.sub(r"^[\s✨🌸🎀#]+", "", title).strip()
        clean_title = re.sub(r"[\s✨🌸🎀]+$", "", clean_title).strip()
        clean_title = strip_private_pricing_data(clean_title)

    if clean_title:
        header_line = f"{tag_line}\n✨ {escape(clean_title)}"
    else:
        header_line = tag_line

    contact_display = (
        contact_username
        if (contact_username.startswith("+") or contact_username.isdigit())
        else f"@{contact_username.lstrip('@')}"
    )

    if adapted_style or reviews_channel:
        # Moonlight aesthetic channel format (compact, blockquote note card)
        sizes_display = format_sizes_display(sizes) if sizes else "Standart"
        rev_handle = reviews_channel.lstrip("@") if reviews_channel else "moonlight_shop_otzv"

        quote_lines = []
        if clean_title:
            quote_lines.append(f"✨ <b>{escape(clean_title)}</b>")
        quote_lines.append(f"🎟️ <b>Narx:</b> {format_price(price)}")
        if is_non_clothing_category(clean_cat):
            if clean_cat in ("kosmetika", "aksessuar", "dekor", "soat"):
                if sizes and sizes != ["Standart"]:
                    quote_lines.append(f"🌸 <b>O'lcham:</b> {sizes_display}")
            else:
                if sizes and sizes != ["Standart"]:
                    quote_lines.append(f"🌸 <b>O'lcham:</b> {sizes_display}")
                else:
                    quote_lines.append(f"🌸 <b>O'lcham:</b> Standart")
        else:
            quote_lines.append(f"🐾 <b>Razmer:</b> {sizes_display}")

        if colors and len(colors) > 0:
            clean_colors = [strip_private_pricing_data(re.sub(r"\s+", " ", c)).strip() for c in colors if c and c.strip()]
            clean_colors = [c for c in clean_colors if c]
            if clean_colors:
                colors_display = ", ".join(clean_colors)
                colors_display = re.sub(r"\s+,", ",", colors_display)
                quote_lines.append(f"🎨 <b>Ranglar:</b> {colors_display}")

        if cargo_rate_avia is not None and cargo_rate_avto is not None:
            avia_str = f"{int(cargo_rate_avia):,}".replace(",", ".")
            avto_str = f"{int(cargo_rate_avto):,}".replace(",", ".")
            quote_lines.append(f"🌸 <b>Kargo (100g):</b> AVIA {avia_str} | AVTO {avto_str}")
            quote_lines.append(f"🚛 <b>Yetkazib berish:</b> {delivery_days_avia} (AVIA) / {delivery_days_avto} (AVTO)")
        else:
            cargo_suffix = " (alohida)" if cargo_separate else ""
            quote_lines.append(f"🌸 <b>Kargo:</b> 100gr – {format_price(cargo_rate)}{cargo_suffix}")
            formatted_delivery = delivery_days if "ichida" in delivery_days or "kun" in delivery_days else f"{delivery_days} ichida"
            quote_lines.append(f"🚛 <b>Yetkazib berish:</b> {formatted_delivery}")

        quote_lines.append(f"✔️ <b>Отзывы:</b> @{rev_handle}")

        inner_quote = "\n".join(quote_lines)
        footer = f"Admin: {contact_display} 🍩"
        if webapp_url:
            footer += f"\n🛍️ <a href=\"{webapp_url}\"><b>Do'konda xarid qilish</b></a>"
        return f"{tag_line}\n\n<blockquote>{inner_quote}</blockquote>\n\n{footer}"

    # Standard / legacy format
    lines = [
        header_line,
        f"💰 Narxi: {format_price(price)}",
        f"📦 Kargo: {format_price(cargo_rate)} / 100g",
        f"⏳ {delivery_days}",
        f"🚚 Dastavka: {delivery_scope}",
        f"Buyurtma berish uchun {contact_display} ga yozing 💌",
    ]
    return "\n".join(lines)


def parse_channel_post(text: str, apply_margin: bool = False) -> Dict[str, Any]:
    """
    Magic shortcut parser: when admin forwards a channel post or pastes text,
    extracts hashtag category, source price, calculates 25%-35% margin retail price,
    extracts sizes, cargo rate, and details.
    """
    result: Dict[str, Any] = {
        "category": "jempir",
        "price": 0,
        "source_price": 0,
        "old_price": None,
        "retail_price": 0,
        "margin_percent": 30.0,
        "title": "",
        "sizes": [],
        "colors": [],
        "cargo_rate": 12000,
        "weight_grams": None,
    }

    if not text:
        return result

    # 1. Extract hashtag (e.g. #scarf, #jempir, #wig, #sumka, #hoodie, #худи, #парик)
    ignored_tags = {"отзыв", "otziv", "otzyv", "skidka", "sale", "aksiya", "yangilik", "repost"}
    all_tags = re.findall(r"#([a-zA-Z0-9_\u0400-\u04FF]+)", text)
    product_tags = [t.lower() for t in all_tags if t.lower() not in ignored_tags]
    if product_tags:
        raw_cat = product_tags[0]
        result["category"] = CYRILLIC_TO_LATIN_CATEGORY.get(raw_cat, raw_cat)
    elif all_tags:
        raw_cat = all_tags[0].lower()
        result["category"] = CYRILLIC_TO_LATIN_CATEGORY.get(raw_cat, raw_cat)

    # 2. Extract sizes (e.g. "Razmer: S-2XL", "👗 Razmer: S, M, L", "👗 S-XXL", "O'lcham: 36-40")
    match_size = re.search(
        r"(?:(?:👗\s*(?:\b(?:razmer(?:lar|i)?|o['’`]?lcham(?:lar|i)?|размер(?:ы)?|size(?:s)?)\b)?)|(?:\b(?:razmer(?:lar|i)?|o['’`]?lcham(?:lar|i)?|размер(?:ы)?|size(?:s)?)\b))\s*[:\-]?\s*([^\n\r]+)",
        text,
        re.IGNORECASE,
    )
    if match_size:
        result["sizes"] = parse_sizes(match_size.group(1))

    # 3. Extract cargo rate if mentioned (e.g. "📦 Kargo: 12.000 so'm / 100g", "12000 / 100g")
    match_cargo = re.search(
        r"(?:📦\s*)?(?:kargo|cargo|доставка)\s*[:\-]?\s*(\d{1,3}(?:[.\s]\d{3})*|\d+)\s*(?:so['’`]?m)?(?:\s*/\s*100g)?",
        text,
        re.IGNORECASE,
    )
    if match_cargo:
        try:
            c_val = int(match_cargo.group(1).replace(".", "").replace(" ", ""))
            if 1000 <= c_val <= 100000:
                result["cargo_rate"] = c_val
        except ValueError:
            pass

    # 4. Extract old / discounted price if mentioned (e.g. "Eski narx: 130.000 so'm", "Old price: 150000")
    old_price = None
    match_old = re.search(
        r"(?:eski\s*narx(?:i)?|old\s*price|старая\s*цена|avvalgi\s*narx(?:i)?)\s*[:\-]?\s*(\d{1,3}(?:[.\s]\d{3})*|\d+)\s*(k|ming)?",
        text,
        re.IGNORECASE,
    )
    if match_old:
        token = match_old.group(1) + (match_old.group(2) or "")
        parsed_old = _parse_price_token(token)
        if parsed_old >= 1000:
            old_price = parsed_old
            result["old_price"] = old_price

    # 5. Extract current source price (ignoring the 'eski narx' line)
    source_price = 0
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    content_lines_no_old = [
        l for l in lines
        if not re.search(r"(?:eski|old|старая|avvalgi)\s*narx", l, re.IGNORECASE)
        and not re.search(r"(?:kargo|cargo|доставка)\s*:", l, re.IGNORECASE)
    ]

    # Check for explicit supplier / original / cost price label first
    for line in content_lines_no_old:
        match_supplier = re.search(
            r"(?:asl\s*narx(?:i)?|ta['’`]?minotchi\s*narx(?:i)?|tan\s*narx(?:i)?|tannarx(?:i)?|optom\s*narx(?:i)?|ulgurji\s*narx(?:i)?)\s*[:\-]?\s*(\d{1,3}(?:[.\s]\d{3})+|\d+)\s*(k|ming)?\s*(?:so['’`]?m|som|сум)?",
            line,
            re.IGNORECASE,
        )
        if match_supplier:
            token = match_supplier.group(1) + (match_supplier.group(2) or "")
            val = _parse_price_token(token)
            if val >= 1000:
                source_price = val
                break

    # Try explicit retail price label on non-old price lines
    if not source_price:
        for line in content_lines_no_old:
            match_price = re.search(
                r"(?:yangi\s*narx(?:i)?|aksiya\s*narx(?:i)?|chegirma\s*narx(?:i)?|💰\s*narxi?|💰|narxi?|narx|цена|price|qiymat(?:i)?)\s*[:\-]?\s*(\d{1,3}(?:[.\s]\d{3})+|\d+)\s*(k|ming)?\s*(?:so['’`]?m|som|сум)?",
                line,
                re.IGNORECASE,
            )
            if match_price:
                token = match_price.group(1) + (match_price.group(2) or "")
                val = _parse_price_token(token)
                if val >= 1000:
                    source_price = val
                    break

    # If not found via explicit label, search lines for currency standalone
    if not source_price:
        for line in content_lines_no_old:
            m_curr = re.search(r"(\d{1,3}(?:[.\s]\d{3})+|\d+)\s*(k|ming)?\s*(?:so['’`]?m|som|сум)", line, re.IGNORECASE)
            if m_curr:
                token = m_curr.group(1) + (m_curr.group(2) or "")
                val = _parse_price_token(token)
                if val >= 1000:
                    source_price = val
                    break

    # If still not found, check for Chinese Yuan / RMB (e.g. '35 yuan', '¥35', '35元', '35 rmb')
    if not source_price:
        for line in content_lines_no_old:
            m_y = re.search(r"(?:[¥￥]\s*(\d+(?:[.,]\d+)?)|(\d+(?:[.,]\d+)?)\s*(?:yuan|юань|rmb|cny|[元块]))", line, re.IGNORECASE)
            if m_y:
                val_str = m_y.group(1) or m_y.group(2)
                try:
                    val = int(round(float(val_str.replace(",", ".")) * 1800))
                    if val >= 1000:
                        source_price = val
                        break
                except ValueError:
                    pass

    # Fallback legacy regex if still not found
    if not source_price:
        for line in content_lines_no_old:
            match_legacy = re.search(r"(\d{1,3}(?:[.\s]\d{3})*|\d+)\s*(k|ming)?\s*(?:so['’`]?m|som|сум)?", line, re.IGNORECASE)
            if match_legacy:
                token = match_legacy.group(1) + (match_legacy.group(2) or "")
                val = _parse_price_token(token)
                if val >= 1000:
                    source_price = val
                    break

    result["source_price"] = source_price
    margin = calculate_margin_percent(source_price)
    result["margin_percent"] = margin
    retail = calculate_retail_price(source_price, margin)
    result["retail_price"] = retail
    result["price"] = retail if apply_margin else source_price

    # 6. Extract colors if present
    match_color = re.search(
        r"(?:🎨\s*)?(?:rang(?:lar)?|color(?:s)?|цвет(?:а)?)\s*[:\-]?\s*([^\n\r]+)",
        text,
        re.IGNORECASE,
    )
    if match_color:
        raw_colors = match_color.group(1).strip()
        result["colors"] = [c.strip() for c in re.split(r"[,;/|]+", raw_colors) if c.strip()]

    # 7. Extract weight if present
    match_weight = re.search(r"(\d+)\s*(?:g|gr|gramm|грамм)\b", text, re.IGNORECASE)
    if match_weight:
        try:
            result["weight_grams"] = int(match_weight.group(1))
        except ValueError:
            pass

    # 8. Extract clean title (never leak supplier price or profit margin)
    for idx, line in enumerate(lines):
        if line.startswith("#"):
            cleaned = re.sub(r"^#[a-zA-Z0-9_\u0400-\u04FF]+\s*", "", line).strip()
            # Remove decorative symbols
            cleaned = re.sub(r"^[\s✨🌸🎀]+", "", cleaned).strip()
            cleaned = re.sub(r"[\s✨🌸🎀]+$", "", cleaned).strip()
            cleaned = strip_private_pricing_data(cleaned)
            if cleaned:
                result["title"] = cleaned[0].upper() + cleaned[1:] if len(cleaned) > 1 else cleaned.upper()
                break
            # Check next line if first line only had hashtag
            if idx + 1 < len(lines):
                next_line = lines[idx + 1]
                if not re.search(r"^(?:💰|Narx|Razmer|Kargo|Yetkazib|Otziv|Admin|📦|👗|⏳|🌸|💌|Eski|Asl|Ta['’`]?minotchi|Tan\s*nar[xh]|Tannar[xh]|Optom|Ulgurji|Foyda|Marja|Ustama|Прибыль|Маржа|Наценка|Себестоимость|Закупка|\+|[¥￥$€]|\d+(?:[.,]\d+)?\s*(?:yuan|юань|rmb|[元块]|so['’`]?m|som|сум|k|ming))", next_line, re.IGNORECASE):
                    c_next = re.sub(r"^[\s✨🌸🎀]+", "", next_line).strip()
                    c_next = re.sub(r"[\s✨🌸🎀]+$", "", c_next).strip()
                    c_next = strip_private_pricing_data(c_next)
                    if c_next and not re.search(r"^(?:[¥￥$€]\s*\d+|\d+(?:[.,]\d+)?\s*(?:yuan|юань|rmb|[元块]|so['’`]?m|som|сум|k|ming))\s*$", c_next, re.IGNORECASE):
                        result["title"] = c_next[0].upper() + c_next[1:] if len(c_next) > 1 else c_next.upper()
                        break

    if not result.get("title"):
        for line in lines:
            if not line.startswith("#") and not re.search(r"^(?:💰|Narx|Razmer|O'lcham|Kargo|Yetkazib|Otziv|Admin|📦|👗|⏳|🌸|💌|Eski|Old|Asl|Ta['’`]?minotchi|Tan\s*nar[xh]|Tannar[xh]|Optom|Ulgurji|Foyda|Marja|Ustama|Прибыль|Маржа|Наценка|Себестоимость|Закупка|\+|[¥￥$€]|\d+(?:[.,]\d+)?\s*(?:yuan|юань|rmb|[元块]|so['’`]?m|som|сум|k|ming))", line, re.IGNORECASE):
                c_line = re.sub(r"^[\s✨🌸🎀#]+", "", line).strip()
                c_line = re.sub(r"[\s✨🌸🎀]+$", "", c_line).strip()
                c_line = strip_private_pricing_data(c_line)
                if c_line and not re.search(r"^(?:[¥￥$€]\s*\d+|\d+(?:[.,]\d+)?\s*(?:yuan|юань|rmb|[元块]|so['’`]?m|som|сум|k|ming))\s*$", c_line, re.IGNORECASE):
                    result["title"] = c_line[0].upper() + c_line[1:] if len(c_line) > 1 else c_line.upper()
                    break

    if not result.get("title"):
        cat_disp = result.get("category") or "kiyim"
        result["title"] = f"{cat_disp.capitalize()} 🌸"

    return result


def build_order_summary(
    order_id: int,
    user_id: int,
    customer_name: str,
    customer_username: Optional[str],
    items: List[Dict[str, Any]],
    total: int,
    estimated_cargo: int = 0,
    contact_username: str = "MOONLIGHT_ADMINNN",
) -> Dict[str, str]:
    """
    Build neat order summary for admin and customer.
    """
    username_display = f"@{customer_username}" if customer_username else "username yo'q"
    user_profile_link = f"<a href='tg://user?id={user_id}'>{escape(customer_name)}</a>"

    item_lines: List[str] = []
    copyable_item_lines: List[str] = []

    for idx, item in enumerate(items, 1):
        title = item.get("title", "Mahsulot")
        qty = item.get("qty", 1)
        price = item.get("price", 0)
        size = item.get("size")
        color = item.get("color")

        attrs = []
        if size:
            attrs.append(f"O'lcham: {size}")
        if color:
            attrs.append(f"Rang: {color}")
        attr_str = f" ({', '.join(attrs)})" if attrs else ""

        subtotal = price * qty
        item_lines.append(f"  {idx}. <b>{escape(str(title))}</b>{escape(attr_str)}\n     {qty} x {format_price(price)} = {format_price(subtotal)}")
        copyable_item_lines.append(f"  {idx}. {title}{attr_str} — {qty} dona ({format_price(subtotal)})")

    items_block = "\n".join(item_lines)
    copyable_items_block = "\n".join(copyable_item_lines)

    cargo_text = f"📦 Taxminiy kargo: <b>{format_price(estimated_cargo)}</b>\n" if estimated_cargo > 0 else ""
    copy_cargo_text = f"📦 Taxminiy kargo: {format_price(estimated_cargo)}\n" if estimated_cargo > 0 else ""

    admin_text = (
        f"🛍️ <b>Yangi buyurtma #{order_id}</b> 🌸\n\n"
        f"👤 <b>Mijoz:</b> {user_profile_link} ({username_display})\n"
        f"🆔 <b>Telegram ID:</b> <code>{user_id}</code>\n\n"
        f"📋 <b>Tanlangan mahsulotlar:</b>\n{items_block}\n\n"
        f"💰 <b>Jami mahsulotlar:</b> <b>{format_price(total)}</b>\n"
        f"{cargo_text}"
        f"💳 100% oldindan to'lov sharti bilan"
    )

    copyable_block = (
        f"🌙 Moonlight Chinese Shop — Buyurtma #{order_id}\n"
        f"Mijoz: {customer_name} ({username_display})\n\n"
        f"{copyable_items_block}\n\n"
        f"Jami: {format_price(total)}\n"
        f"{copy_cargo_text}"
    )

    contact_display = contact_username if (contact_username.startswith("+") or contact_username.isdigit()) else f"@{contact_username.lstrip('@')}"

    customer_text = (
        f"🌸 <b>Rahmat, {escape(customer_name)}!</b> 💗\n\n"
        f"Sizning buyurtmangiz (#{order_id}) qabul qilindi. Admin tez orada siz bilan bog'lanadi!\n\n"
        f"📋 <b>Buyurtma tafsilotlari:</b>\n{items_block}\n\n"
        f"💰 <b>Jami summa:</b> <b>{format_price(total)}</b>\n"
        f"{cargo_text}\n"
        f"💌 <b>Tezroq buyurtma berish uchun quyidagi matnni nusxalab {contact_display} ga yuborishingiz mumkin:</b>\n\n"
        f"<code>{escape(copyable_block)}</code>"
    )

    return {
        "admin_text": admin_text,
        "customer_text": customer_text,
        "copyable_block": copyable_block,
    }
