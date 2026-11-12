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
    "косметика": "kosmetika",
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


def format_sizes_display(sizes: Optional[List[str]]) -> str:
    """Format list of sizes for display, e.g. ['S', 'M', 'L', 'XL', '2XL'] -> 'S-2XL'."""
    if not sizes:
        return ""
    # If matches a continuous standard range, format as Start-End
    if len(sizes) >= 3 and all(s in STANDARD_SIZES for s in sizes):
        indices = [STANDARD_SIZES.index(s) for s in sizes]
        if indices == list(range(indices[0], indices[-1] + 1)):
            return f"{sizes[0]}-{sizes[-1]}"
    # Numeric range
    if len(sizes) >= 3 and all(s.isdigit() for s in sizes):
        nums = [int(s) for s in sizes]
        if nums == list(range(nums[0], nums[-1] + 1)):
            return f"{sizes[0]}-{sizes[-1]}"
    return ", ".join(sizes)


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


def calculate_retail_price(source_price: int, margin_percent: Optional[float] = None) -> int:
    """
    Adds 25%-35% profit margin to source price and rounds to clean 1,000 so'm.
    Example: 95.000 + 30% = 123.500 -> 124.000 so'm.
    """
    if not source_price or source_price <= 0:
        return 0
    if margin_percent is None:
        margin_percent = calculate_margin_percent(source_price)
    margin_percent = max(25.0, min(35.0, float(margin_percent)))
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


def _parse_price_token(token: str) -> int:
    """Helper to convert price token like '95.000', '95 000', '95k', '95ming', '95000' to int."""
    if not token:
        return 0
    clean = token.lower().strip()
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
    reviews_channel: Optional[str] = None,
    cargo_separate: bool = False,
    adapted_style: bool = False,
) -> str:
    """
    Build channel post caption.
    Supports both legacy format (for backward compatibility) and
    adapted Moonlight brand format with sizes, reviews channel, and separate cargo.
    When cargo_rate_avia & cargo_rate_avto are provided, it presents both AVIA and AVTO tariffs.
    """
    clean_cat = category_slug.replace("#", "").strip()
    tag_line = f"#{clean_cat} 🌸"

    clean_title = ""
    if title:
        # Strip leading & trailing decorative flowers/sparkles/hashes
        clean_title = re.sub(r"^[\s✨🌸🎀#]+", "", title).strip()
        clean_title = re.sub(r"[\s✨🌸🎀]+$", "", clean_title).strip()

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
        # Moonlight adapted channel format
        cargo_suffix = " (alohida)" if cargo_separate else ""
        lines = [
            header_line,
            f"💰 Narxi: {format_price(price)}",
        ]
        sizes_display = format_sizes_display(sizes) if sizes else "Standart"
        lines.append(f"👗 Razmer: {sizes_display}")

        if cargo_rate_avia is not None and cargo_rate_avto is not None:
            # Dual AVIA + AVTO breakdown
            lines.append(
                f"📦 Kargo (har 100g uchun alohida):\n"
                f"  ✈️ AVIA: {format_price(cargo_rate_avia)} / 100g ({delivery_days_avia})\n"
                f"  🚗 AVTO: {format_price(cargo_rate_avto)} / 100g ({delivery_days_avto})"
            )
        else:
            lines.append(f"📦 Kargo: {format_price(cargo_rate)} / 100g{cargo_suffix}")
            formatted_delivery = delivery_days if "ichida" in delivery_days or "kun" in delivery_days else f"{delivery_days} ichida"
            lines.append(f"⏳ Yetkazib berish: {formatted_delivery}")

        rev_handle = reviews_channel.lstrip("@") if reviews_channel else "moonlight_shop_otzv"
        lines.append(f"🌸 Otzivlar: @{rev_handle}")
        lines.append(f"💌 Admin: {contact_display}")
        return "\n".join(lines)

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

    # Try explicit price label on non-old price lines first
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

    # 8. Extract clean title
    for idx, line in enumerate(lines):
        if line.startswith("#"):
            cleaned = re.sub(r"^#[a-zA-Z0-9_\u0400-\u04FF]+\s*", "", line).strip()
            # Remove decorative symbols
            cleaned = re.sub(r"^[\s✨🌸🎀]+", "", cleaned).strip()
            cleaned = re.sub(r"[\s✨🌸🎀]+$", "", cleaned).strip()
            if cleaned:
                result["title"] = cleaned
                break
            # Check next line if first line only had hashtag
            if idx + 1 < len(lines):
                next_line = lines[idx + 1]
                if not re.search(r"^(?:💰|Narx|Razmer|Kargo|Yetkazib|Otziv|Admin|📦|👗|⏳|🌸|💌|Eski)", next_line, re.IGNORECASE):
                    c_next = re.sub(r"^[\s✨🌸🎀]+", "", next_line).strip()
                    c_next = re.sub(r"[\s✨🌸🎀]+$", "", c_next).strip()
                    if c_next:
                        result["title"] = c_next
                        break

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
