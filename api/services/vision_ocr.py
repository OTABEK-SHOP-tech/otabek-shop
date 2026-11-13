import base64
import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import httpx

from api.config import settings
from api.services.formatters import (
    CYRILLIC_TO_LATIN_CATEGORY,
    calculate_margin_percent,
    calculate_retail_price,
    parse_sizes,
)

logger = logging.getLogger(__name__)

DEFAULT_GEMINI_MODEL = "gemini-2.0-flash"
FALLBACK_GEMINI_MODEL = "gemini-1.5-flash"
GEMINI_ENDPOINT_TEMPLATE = (
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
)

# Categories that naturally do not have garment sizing (or are one-size)
ONE_SIZE_CATEGORIES = {"sumka", "aksessuar", "kosmetika", "wig", "scarf"}

# Comprehensive multilingual mapping for aesthetic Uzbek color names with emoji
COLOR_MAP = {
    # Chinese
    "粉色": "Pushti 🌸",
    "粉红": "Pushti 🌸",
    "粉红色": "Pushti 🌸",
    "粉": "Pushti 🌸",
    "浅粉": "Pushti 🌸",
    "浅粉色": "Pushti 🌸",
    "藕粉": "Pushti 🌸",
    "藕粉色": "Pushti 🌸",
    "豆沙": "Pushti 🌸",
    "豆沙粉": "Pushti 🌸",
    "豆沙色": "Pushti 🌸",
    "烟灰粉": "Pushti 🌸",
    "白色": "Oq 🤍",
    "白": "Oq 🤍",
    "乳白": "Oq 🤍",
    "纯白": "Oq 🤍",
    "象牙白": "Oq 🤍",
    "黑色": "Qora 🖤",
    "黑": "Qora 🖤",
    "炭黑": "Qora 🖤",
    "墨黑": "Qora 🖤",
    "牛仔黑": "Qora 🖤",
    "蓝色": "Ko'k 💙",
    "蓝": "Ko'k 💙",
    "浅蓝": "Havorang 🩵",
    "浅蓝色": "Havorang 🩵",
    "天蓝": "Havorang 🩵",
    "天蓝色": "Havorang 🩵",
    "雾霾蓝": "Havorang 🩵",
    "牛仔蓝": "Ko'k 💙",
    "宝蓝": "To'q ko'k 💙",
    "深蓝": "To'q ko'k 💙",
    "深蓝色": "To'q ko'k 💙",
    "藏青": "To'q ko'k 💙",
    "藏青色": "To'q ko'k 💙",
    "米色": "Bej 🤎",
    "米白": "Oq 🤍",
    "卡其": "Bej 🤎",
    "卡其色": "Bej 🤎",
    "驼色": "Bej 🤎",
    "深驼色": "To'q bej 🤎",
    "浅驼色": "Bej 🤎",
    "燕麦": "Bej 🤎",
    "燕麦色": "Bej 🤎",
    "奶茶": "Bej 🤎",
    "奶茶色": "Bej 🤎",
    "绿色": "Yashil 💚",
    "绿": "Yashil 💚",
    "草绿": "Yashil 💚",
    "草绿色": "Yashil 💚",
    "墨绿": "To'q yashil 💚",
    "墨绿色": "To'q yashil 💚",
    "浅绿": "Yashil 💚",
    "军绿": "Xaki 🤎",
    "军绿色": "Xaki 🤎",
    "牛油果绿": "Yashil 💚",
    "薄荷绿": "Yalpiz rang 🌿",
    "红色": "Qizil ❤️",
    "红": "Qizil ❤️",
    "大红": "Qizil ❤️",
    "大红色": "Qizil ❤️",
    "砖红": "Qizil ❤️",
    "砖红色": "Qizil ❤️",
    "酒红": "To'q qizil ❤️",
    "酒红色": "To'q qizil ❤️",
    "黄色": "Sariq 💛",
    "黄": "Sariq 💛",
    "姜黄": "Sariq 💛",
    "姜黄色": "Sariq 💛",
    "柠檬黄": "Sariq 💛",
    "紫色": "Binafsha 💜",
    "紫": "Binafsha 💜",
    "浅紫": "Binafsha 💜",
    "浅紫色": "Binafsha 💜",
    "香芋紫": "Binafsha 💜",
    "灰色": "Kulrang 🩶",
    "灰": "Kulrang 🩶",
    "深灰": "To'q kulrang 🩶",
    "浅灰": "Kulrang 🩶",
    "花灰": "Kulrang 🩶",
    "花灰色": "Kulrang 🩶",
    "银灰": "Kumushrang 🤍",
    "棕色": "Jigarrang 🤎",
    "咖啡": "Jigarrang 🤎",
    "咖啡色": "Jigarrang 🤎",
    "焦糖": "Jigarrang 🤎",
    "焦糖色": "Jigarrang 🤎",
    "杏色": "Krem rang 🍦",
    "奶油": "Krem rang 🍦",
    "奶油色": "Krem rang 🍦",
    "橙色": "Sabzirang 🧡",
    "橘色": "Sabzirang 🧡",
    "桔色": "Sabzirang 🧡",
    "金色": "Oltinrang 💛",
    "金": "Oltinrang 💛",
    "香槟": "Oltinrang 💛",
    "香槟金": "Oltinrang 💛",
    "银色": "Kumushrang 🤍",
    "银": "Kumushrang 🤍",

    # Russian
    "розовый": "Pushti 🌸",
    "розовая": "Pushti 🌸",
    "розовое": "Pushti 🌸",
    "светло-розовый": "Pushti 🌸",
    "светло-розовая": "Pushti 🌸",
    "пудровый": "Pushti 🌸",
    "пудровая": "Pushti 🌸",
    "пудра": "Pushti 🌸",
    "белый": "Oq 🤍",
    "белая": "Oq 🤍",
    "белое": "Oq 🤍",
    "молочный": "Krem rang 🍦",
    "молочная": "Krem rang 🍦",
    "черный": "Qora 🖤",
    "чёрный": "Qora 🖤",
    "черная": "Qora 🖤",
    "чёрная": "Qora 🖤",
    "черное": "Qora 🖤",
    "голубой": "Havorang 🩵",
    "голубая": "Havorang 🩵",
    "голубое": "Havorang 🩵",
    "светло-голубой": "Havorang 🩵",
    "синий": "Ko'k 💙",
    "синяя": "Ko'k 💙",
    "синее": "Ko'k 💙",
    "темно-синий": "To'q ko'k 💙",
    "тёмно-синий": "To'q ko'k 💙",
    "бежевый": "Bej 🤎",
    "бежевая": "Bej 🤎",
    "зеленый": "Yashil 💚",
    "зелёный": "Yashil 💚",
    "зелена": "Yashil 💚",
    "зеленая": "Yashil 💚",
    "зелёная": "Yashil 💚",
    "темно-зеленый": "To'q yashil 💚",
    "изумрудный": "Yashil 💚",
    "изумрудная": "Yashil 💚",
    "оливковый": "Zaytun rang 🫒",
    "оливковая": "Zaytun rang 🫒",
    "красный": "Qizil ❤️",
    "красная": "Qizil ❤️",
    "бордовый": "To'q qizil ❤️",
    "бордовая": "To'q qizil ❤️",
    "бордо": "To'q qizil ❤️",
    "желтый": "Sariq 💛",
    "жёлтый": "Sariq 💛",
    "желтая": "Sariq 💛",
    "горчичный": "Sariq 💛",
    "фиолетовый": "Binafsha 💜",
    "фиолетовая": "Binafsha 💜",
    "сиреневый": "Binafsha 💜",
    "сиреневая": "Binafsha 💜",
    "лавандовый": "Binafsha 💜",
    "лавандовая": "Binafsha 💜",
    "лиловый": "Binafsha 💜",
    "серый": "Kulrang 🩶",
    "серая": "Kulrang 🩶",
    "светло-серый": "Kulrang 🩶",
    "темно-серый": "To'q kulrang 🩶",
    "тёмно-серый": "To'q kulrang 🩶",
    "коричневый": "Jigarrang 🤎",
    "коричневая": "Jigarrang 🤎",
    "шоколадный": "Jigarrang 🤎",
    "шоколадная": "Jigarrang 🤎",
    "кофейный": "Jigarrang 🤎",
    "кремовый": "Krem rang 🍦",
    "кремовая": "Krem rang 🍦",
    "оранжевый": "Sabzirang 🧡",
    "оранжевая": "Sabzirang 🧡",
    "персиковый": "Shaftolirang 🍑",
    "персиковая": "Shaftolirang 🍑",
    "хаки": "Xaki 🤎",
    "мятный": "Yalpiz rang 🌿",
    "мятная": "Yalpiz rang 🌿",
    "золотой": "Oltinrang 💛",
    "золотая": "Oltinrang 💛",
    "серебристый": "Kumushrang 🤍",
    "серебристая": "Kumushrang 🤍",

    # English
    "pink": "Pushti 🌸",
    "light pink": "Pushti 🌸",
    "baby pink": "Pushti 🌸",
    "dusty pink": "Pushti 🌸",
    "white": "Oq 🤍",
    "ivory": "Krem rang 🍦",
    "off-white": "Oq 🤍",
    "black": "Qora 🖤",
    "light blue": "Havorang 🩵",
    "baby blue": "Havorang 🩵",
    "sky blue": "Havorang 🩵",
    "blue": "Ko'k 💙",
    "dark blue": "To'q ko'k 💙",
    "navy": "To'q ko'k 💙",
    "navy blue": "To'q ko'k 💙",
    "beige": "Bej 🤎",
    "nude": "Bej 🤎",
    "camel": "Bej 🤎",
    "oatmeal": "Bej 🤎",
    "khaki": "Bej 🤎",
    "green": "Yashil 💚",
    "dark green": "To'q yashil 💚",
    "light green": "Yashil 💚",
    "olive": "Zaytun rang 🫒",
    "red": "Qizil ❤️",
    "wine red": "To'q qizil ❤️",
    "wine": "To'q qizil ❤️",
    "burgundy": "To'q qizil ❤️",
    "maroon": "To'q qizil ❤️",
    "yellow": "Sariq 💛",
    "mustard": "Sariq 💛",
    "purple": "Binafsha 💜",
    "violet": "Binafsha 💜",
    "lilac": "Binafsha 💜",
    "lavender": "Binafsha 💜",
    "grey": "Kulrang 🩶",
    "gray": "Kulrang 🩶",
    "light grey": "Kulrang 🩶",
    "dark grey": "To'q kulrang 🩶",
    "charcoal": "To'q kulrang 🩶",
    "brown": "Jigarrang 🤎",
    "coffee": "Jigarrang 🤎",
    "mocha": "Jigarrang 🤎",
    "chocolate": "Jigarrang 🤎",
    "cream": "Krem rang 🍦",
    "apricot": "Krem rang 🍦",
    "orange": "Sabzirang 🧡",
    "peach": "Shaftolirang 🍑",
    "coral": "Sabzirang 🧡",
    "gold": "Oltinrang 💛",
    "silver": "Kumushrang 🤍",
    "mint": "Yalpiz rang 🌿",
    "teal": "Feruza rang 🩵",
    "turquoise": "Feruza rang 🩵",

    # Uzbek
    "pushti": "Pushti 🌸",
    "och pushti": "Pushti 🌸",
    "oq": "Oq 🤍",
    "sutrang": "Krem rang 🍦",
    "qora": "Qora 🖤",
    "havorang": "Havorang 🩵",
    "havo rang": "Havorang 🩵",
    "ko'k": "Ko'k 💙",
    "kok": "Ko'k 💙",
    "to'q ko'k": "To'q ko'k 💙",
    "toq kok": "To'q ko'k 💙",
    "bej": "Bej 🤎",
    "och bej": "Bej 🤎",
    "to'q bej": "To'q bej 🤎",
    "yashil": "Yashil 💚",
    "och yashil": "Yashil 💚",
    "to'q yashil": "To'q yashil 💚",
    "zaytun": "Zaytun rang 🫒",
    "zaytun rang": "Zaytun rang 🫒",
    "xaki": "Xaki 🤎",
    "qizil": "Qizil ❤️",
    "to'q qizil": "To'q qizil ❤️",
    "sariq": "Sariq 💛",
    "binafsha": "Binafsha 💜",
    "kulrang": "Kulrang 🩶",
    "kul rang": "Kulrang 🩶",
    "to'q kulrang": "To'q kulrang 🩶",
    "jigarrang": "Jigarrang 🤎",
    "jigar rang": "Jigarrang 🤎",
    "krem": "Krem rang 🍦",
    "krem rang": "Krem rang 🍦",
    "sabzirang": "Sabzirang 🧡",
    "shaftolirang": "Shaftolirang 🍑",
    "shaftoli rang": "Shaftolirang 🍑",
    "oltinrang": "Oltinrang 💛",
    "kumushrang": "Kumushrang 🤍",
    "feruza": "Feruza rang 🩵",
}

# Multilingual category slug mapping
CATEGORY_KEYWORDS = {
    # Hoodie / sweatshirts
    "hoodie": "hoodie",
    "hudi": "hoodie",
    "толстовка": "hoodie",
    "худи": "hoodie",
    "свитшот": "hoodie",
    "sweatshirt": "hoodie",
    "卫衣": "hoodie",
    "连帽衫": "hoodie",
    # Sweater / jumper / cardigan
    "jempir": "jempir",
    "sviter": "jempir",
    "sweater": "jempir",
    "jumper": "jempir",
    "cardigan": "jempir",
    "kardigan": "jempir",
    "knitwear": "jempir",
    "свитер": "jempir",
    "джемпер": "jempir",
    "кофта": "jempir",
    "кардиган": "jempir",
    "водолазка": "jempir",
    "毛衣": "jempir",
    "针织衫": "jempir",
    "开衫": "jempir",
    # Dress
    "koylak": "koylak",
    "ko'ylak": "koylak",
    "dress": "koylak",
    "платье": "koylak",
    "сарафан": "koylak",
    "连衣裙": "koylak",
    "裙子": "koylak",
    # Skirt
    "yubka": "yubka",
    "skirt": "yubka",
    "юбка": "yubka",
    "半身裙": "yubka",
    # Bag
    "sumka": "sumka",
    "bag": "sumka",
    "handbag": "sumka",
    "backpack": "sumka",
    "crossbody": "sumka",
    "сумка": "sumka",
    "сумочка": "sumka",
    "рюкзак": "sumka",
    "клатч": "sumka",
    "шоппер": "sumka",
    "包": "sumka",
    "包包": "sumka",
    "女包": "sumka",
    "手提包": "sumka",
    "单肩包": "sumka",
    "斜挎包": "sumka",
    # Shoes / footwear
    "shoes": "shoes",
    "sneakers": "shoes",
    "boots": "shoes",
    "footwear": "shoes",
    "loafers": "shoes",
    "sandals": "shoes",
    "обувь": "shoes",
    "кроссовки": "shoes",
    "кеды": "shoes",
    "туфли": "shoes",
    "ботинки": "shoes",
    "лоферы": "shoes",
    "сапоги": "shoes",
    "босоножки": "shoes",
    "сандалии": "shoes",
    "poyabzal": "shoes",
    "krossovka": "shoes",
    "tufli": "shoes",
    "oyoqkiyim": "shoes",
    "botinka": "shoes",
    "鞋": "shoes",
    "鞋子": "shoes",
    "运动鞋": "shoes",
    "帆布鞋": "shoes",
    "单鞋": "shoes",
    "靴子": "shoes",
    # Pants / jeans
    "shim": "shim",
    "pants": "shim",
    "trousers": "shim",
    "jeans": "shim",
    "leggings": "shim",
    "брюки": "shim",
    "штаны": "shim",
    "джинсы": "shim",
    "лосины": "shim",
    "леггинсы": "shim",
    "шорты": "shim",
    "jinsi": "shim",
    "shortik": "shim",
    "裤子": "shim",
    "牛仔裤": "shim",
    "阔腿裤": "shim",
    "休闲裤": "shim",
    # T-shirt / top
    "futbolka": "futbolka",
    "t-shirt": "futbolka",
    "tee": "futbolka",
    "top": "futbolka",
    "футболка": "futbolka",
    "топ": "futbolka",
    "майка": "futbolka",
    "лонгслив": "futbolka",
    "tshirt": "futbolka",
    "t恤": "futbolka",
    "短袖": "futbolka",
    # Jacket
    "kurtka": "kurtka",
    "jacket": "kurtka",
    "куртка": "kurtka",
    "ветровка": "kurtka",
    "бомбер": "kurtka",
    "пуховик": "kurtka",
    "外套": "kurtka",
    "夹克": "kurtka",
    # Coat
    "palto": "palto",
    "coat": "palto",
    "overcoat": "palto",
    "trench": "palto",
    "пальто": "palto",
    "плащ": "palto",
    "тренч": "palto",
    "大衣": "palto",
    "毛呢大衣": "palto",
    "羽绒服": "palto",
    # Wig
    "wig": "wig",
    "parik": "wig",
    "парик": "wig",
    "шиньон": "wig",
    "假发": "wig",
    "发套": "wig",
    # Scarf
    "scarf": "scarf",
    "sharf": "scarf",
    "шарф": "scarf",
    "платок": "scarf",
    "палантин": "scarf",
    "romol": "scarf",
    "ro'mol": "scarf",
    "围巾": "scarf",
    "披肩": "scarf",
    # Accessories
    "aksessuar": "aksessuar",
    "accessories": "aksessuar",
    "аксессуар": "aksessuar",
    "аксессуары": "aksessuar",
    "бижутерия": "aksessuar",
    "ремень": "aksessuar",
    "kamar": "aksessuar",
    "ko'zoynak": "aksessuar",
    "ochki": "aksessuar",
    "soat": "aksessuar",
    "bosh kiyim": "aksessuar",
    "shapka": "aksessuar",
    "kepka": "aksessuar",
    "panama": "aksessuar",
    "饰品": "aksessuar",
    "配饰": "aksessuar",
    "首饰": "aksessuar",
    # Cosmetics
    "kosmetika": "kosmetika",
    "cosmetics": "kosmetika",
    "makeup": "kosmetika",
    "косметика": "kosmetika",
    "помада": "kosmetika",
    "крем": "kosmetika",
    "atir": "kosmetika",
    "parfyum": "kosmetika",
    "духи": "kosmetika",
    "美妆": "kosmetika",
    "化妆品": "kosmetika",
}


def convert_currency_to_uzs(
    raw_price: Union[float, int, str],
    currency: Optional[str] = None,
    yuan_rate: Optional[int] = None,
    usd_rate: Optional[int] = None,
    rub_rate: Optional[int] = None,
) -> int:
    """
    Converts foreign currencies to Uzbek So'm (UZS).
    - Chinese Yuan (¥ / RMB / CNY) -> default 1,800 UZS/Yuan
    - USD ($) -> default 12,900 UZS/USD
    - Russian Ruble (₽ / RUB) -> default 140 UZS/RUB
    - Uzbek So'm -> 1:1
    """
    try:
        val = float(raw_price)
    except (ValueError, TypeError):
        return 0

    if val <= 0:
        return 0

    y_rate = yuan_rate or getattr(settings, "YUAN_TO_UZS_RATE", 1800)
    u_rate = usd_rate or getattr(settings, "USD_TO_UZS_RATE", 12900)
    r_rate = rub_rate or getattr(settings, "RUB_TO_UZS_RATE", 140)

    curr_str = (currency or "").strip().upper()

    # Chinese Yuan
    if any(k in curr_str for k in ("CNY", "RMB", "YUAN", "¥", "￥", "元", "块")):
        return int(round(val * y_rate))

    # US Dollar
    if any(k in curr_str for k in ("USD", "$", "DOLLAR")):
        return int(round(val * u_rate))

    # Russian Ruble
    if any(k in curr_str for k in ("RUB", "₽", "РУБ", "РУБЛЬ")):
        return int(round(val * r_rate))

    # Uzbek So'm
    if any(k in curr_str for k in ("UZS", "SO'M", "SOM", "СУМ", "СЎМ")):
        return int(round(val))

    # Fallback heuristic: small numbers (< 1000) are almost always Chinese Yuan in Chinese e-commerce
    if val < 1000:
        return int(round(val * y_rate))

    return int(round(val))


def normalize_color(color_name: str) -> str:
    """
    Normalizes a single color token into aesthetic Uzbek name with emoji.
    Example: '粉色' -> 'Pushti 🌸', 'black' -> 'Qora 🖤', 'белый' -> 'Oq 🤍'
    """
    if not color_name:
        return ""
    clean = color_name.strip()
    if not clean:
        return ""

    # If it already has an emoji, normalize whitespace and return
    if any(c in clean for c in "🌸🤍🖤🩵🤎💚❤️💛💜🩶💙🍦🧡🌿🍑🫒"):
        return clean

    # Strip bracketed modifiers like 【加绒】, (单件), (春款), [套装], etc.
    clean = re.sub(r"[（(【\[][^）)】\]]*[）)】\]]", "", clean).strip()
    # Strip common package/garment suffixes in Chinese (e.g. 黑色单件 -> 黑色)
    clean = re.sub(r"(?:单件|套装|加绒|薄款|两件套)$", "", clean).strip()
    if not clean:
        return ""

    lower = clean.lower()

    # Exact dictionary match
    if lower in COLOR_MAP:
        return COLOR_MAP[lower]

    # Clean punctuation and check again
    sub_clean = re.sub(r"[^\w\s\u0400-\u04FF\u4e00-\u9fff]", "", lower).strip()
    if sub_clean in COLOR_MAP:
        return COLOR_MAP[sub_clean]

    # Partial / substring check
    for key, mapped in COLOR_MAP.items():
        if key in sub_clean:
            return mapped

    # Fallback: capitalize clean name with cute flower
    cap = clean.capitalize()
    return f"{cap} 🌸"


def normalize_colors(colors_input: Union[str, List[str], None]) -> List[str]:
    """
    Normalizes a list or string of colors into aesthetic Uzbek color names.
    """
    if not colors_input:
        return []

    tokens: List[str] = []
    if isinstance(colors_input, str):
        # Split by comma, slash, semicolon, pipe or newline
        parts = re.split(r"[,;/|\n\r]+", colors_input)
        tokens = [p.strip() for p in parts if p.strip()]
    elif isinstance(colors_input, (list, tuple)):
        for item in colors_input:
            if isinstance(item, str):
                parts = re.split(r"[,;/|\n\r]+", item)
                tokens.extend([p.strip() for p in parts if p.strip()])

    result: List[str] = []
    for t in tokens:
        norm = normalize_color(t)
        if norm and norm not in result:
            result.append(norm)

    return result


def normalize_sizes(sizes_input: Union[str, List[str], None]) -> List[str]:
    """
    Normalizes size list from AI extraction.
    Translates Chinese '均码' / Russian 'Стандарт' / English 'Free size' -> 'Standart'.
    Cleans Chinese size suffixes (S码 -> S, 36码 -> 36) and weight notes (M码【建议90-105斤】 -> M).
    Expands ranges like 'S-2XL' or '36-40'.
    """
    if not sizes_input:
        return []

    raw_tokens: List[str] = []
    if isinstance(sizes_input, str):
        parts = re.split(r"[,;/|\n\r]+", sizes_input)
        raw_tokens = [p.strip() for p in parts if p.strip()]
    elif isinstance(sizes_input, (list, tuple)):
        for item in sizes_input:
            if isinstance(item, str):
                parts = re.split(r"[,;/|\n\r]+", item)
                raw_tokens.extend([p.strip() for p in parts if p.strip()])

    result: List[str] = []
    for token in raw_tokens:
        # 1. Strip bracketed weight annotations (e.g. "【建议90-105斤】", "(80-120斤)", "【适合45-55kg】")
        tok = re.sub(
            r"[（(【\[][^）)】\]]*(?:斤|kg|建议|适合|вес|weight|recom)[^）)】\]]*[）)】\]]",
            "",
            token,
            flags=re.IGNORECASE,
        ).strip()

        # 2. Check for standard / one-size keywords
        lower = tok.lower()
        if any(
            k in lower
            for k in (
                "均码",
                "一码",
                "统一码",
                "通码",
                "无尺码",
                "大码",
                "加肥加大",
                "стандарт",
                "единый",
                "free size",
                "freesize",
                "one size",
                "onesize",
                "standart",
                "standard",
                "oversize",
            )
        ):
            if "Standart" not in result:
                result.append("Standart")
            continue

        # 3. Clean Chinese size prefixes (尺码:, 尺寸:) and suffixes (码, 号)
        c = re.sub(r"^(?:尺码|尺寸|规格|码数)[:：\s]*", "", tok).strip()
        c = re.sub(r"(?:[码号]$|\s*[码号]\b)", "", c).strip()
        c = c.replace("至", "-").replace("~", "-")

        # 4. Use existing formatters parse_sizes for range or letter/number tokens
        parsed = parse_sizes(c)
        for s in parsed:
            if s not in result:
                result.append(s)

    return result


def normalize_category(category_input: Optional[str]) -> str:
    """
    Matches category slug across languages. Default 'kiyim'.
    """
    if not category_input:
        return "kiyim"
    clean = category_input.strip().lower().replace("#", "")

    # Direct keyword match
    if clean in CATEGORY_KEYWORDS:
        return CATEGORY_KEYWORDS[clean]

    # Cyrillic lookup
    if clean in CYRILLIC_TO_LATIN_CATEGORY:
        return CYRILLIC_TO_LATIN_CATEGORY[clean]

    # Partial substring check
    for kw, slug in CATEGORY_KEYWORDS.items():
        if kw in clean:
            return slug

    return clean if len(clean) >= 3 else "kiyim"


def parse_vision_response(
    data: Dict[str, Any],
    yuan_rate: Optional[int] = None,
    usd_rate: Optional[int] = None,
    rub_rate: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Normalizes parsed JSON response from Gemini Vision:
    calculates source price, 25-35% profit margin, retail price,
    aesthetic sizes and colors.
    """
    raw_price = data.get("raw_price")
    currency = data.get("currency")

    # If raw_price was parsed as string or has currency symbols, extract currency and number
    if isinstance(raw_price, str):
        clean_raw = raw_price.strip()
        # Collapse spaces between digits (e.g. "1 500" -> "1500", "120 000" -> "120000")
        clean_raw = re.sub(r"(?<=\d)[\s\xa0]+(?=\d)", "", clean_raw)

        if not currency:
            m_curr = re.search(
                r"(cny|rmb|yuan|[¥￥元块]|usd|\$|rub|₽|руб(?:ль)?|uzs|so['’`]?m|som|сум|сўм)",
                clean_raw,
                re.IGNORECASE,
            )
            if m_curr:
                matched_sym = m_curr.group(1).upper()
                if any(k in matched_sym for k in ("CNY", "RMB", "YUAN", "¥", "￥", "元", "块")):
                    currency = "CNY"
                elif any(k in matched_sym for k in ("USD", "$")):
                    currency = "USD"
                elif any(k in matched_sym for k in ("RUB", "₽", "РУБ")):
                    currency = "RUB"
                elif any(k in matched_sym for k in ("UZS", "SO", "SOM", "СУМ", "СЎМ")):
                    currency = "UZS"

        # Check thousands dot formatting (e.g. 120.000 or 95.000 so'm)
        m_thousands = re.search(r"(?:^|[^\d.])(\d{1,3}(?:\.\d{3})+)(?:[^\d.]|$)", clean_raw)
        if m_thousands and (
            currency in ("UZS", "RUB")
            or not currency
            or any(k in clean_raw.lower() for k in ("so'm", "som", "сум", "сўм"))
        ):
            raw_price = float(m_thousands.group(1).replace(".", ""))
        else:
            # If it's a price range (e.g. "29.9 - 39.9" or "¥29.9~¥39.9"), pick the first number
            m_num = re.search(r"(\d+(?:[.,]\d+)?)", clean_raw)
            if m_num:
                try:
                    raw_price = float(m_num.group(1).replace(",", "."))
                except ValueError:
                    raw_price = 0.0
            else:
                raw_price = 0.0

    num_price = float(raw_price or 0.0)

    # Normalize currency code string
    curr_upper = (currency or "").strip().upper()
    if any(k in curr_upper for k in ("CNY", "RMB", "YUAN", "¥", "￥", "元", "块")):
        norm_currency = "CNY"
    elif any(k in curr_upper for k in ("USD", "$")):
        norm_currency = "USD"
    elif any(k in curr_upper for k in ("RUB", "₽", "РУБ")):
        norm_currency = "RUB"
    elif any(k in curr_upper for k in ("UZS", "SO", "SOM", "СУМ", "СЎМ")):
        norm_currency = "UZS"
    else:
        norm_currency = "CNY" if num_price < 1000 else "UZS"

    source_price = 0
    retail_price = 0
    margin_percent = 30.0

    if num_price > 0:
        source_price = convert_currency_to_uzs(
            num_price,
            currency=norm_currency,
            yuan_rate=yuan_rate,
            usd_rate=usd_rate,
            rub_rate=rub_rate,
        )
        margin_percent = calculate_margin_percent(source_price)
        retail_price = calculate_retail_price(source_price, margin_percent)

    cat_slug = normalize_category(data.get("category"))
    sizes = normalize_sizes(data.get("sizes"))
    # If the category is naturally a one-size item and sizes was empty, default to Standart
    if not sizes and cat_slug in ONE_SIZE_CATEGORIES:
        sizes = ["Standart"]

    colors = normalize_colors(data.get("colors"))

    title = (data.get("title") or "").strip()
    # Strip leading/trailing decorative symbols
    title = re.sub(r"^[\s✨🌸🎀#]+", "", title).strip()
    title = re.sub(r"[\s✨🌸🎀]+$", "", title).strip()
    if not title:
        title = f"{cat_slug.capitalize()} 🌸"

    cargo_rate = data.get("cargo_rate")
    if cargo_rate is not None:
        try:
            cargo_rate = int(cargo_rate)
        except (ValueError, TypeError):
            cargo_rate = 12000
    else:
        cargo_rate = 12000

    weight_grams = data.get("weight_grams")
    if weight_grams is not None:
        try:
            weight_grams = int(weight_grams)
        except (ValueError, TypeError):
            weight_grams = None

    return {
        "success": True,
        "title": title,
        "category": cat_slug,
        "source_price": source_price,
        "retail_price": retail_price,
        "price": retail_price,
        "margin_percent": margin_percent,
        "raw_price": num_price,
        "currency": norm_currency,
        "sizes": sizes,
        "colors": colors,
        "cargo_rate": cargo_rate,
        "weight_grams": weight_grams,
        "raw_data": data,
    }


def _detect_image_mime(image_bytes: bytes) -> str:
    """Detects image mime type from magic bytes."""
    if image_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if image_bytes.startswith(b"RIFF") and b"WEBP" in image_bytes[:16]:
        return "image/webp"
    if image_bytes.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    return "image/jpeg"


async def extract_product_from_image(
    image_input: Union[bytes, str, Path, Any],
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    timeout: float = 15.0,
    yuan_rate: Optional[int] = None,
    usd_rate: Optional[int] = None,
    rub_rate: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Multimodal AI Vision extraction for e-commerce screenshots (Pinduoduo, 1688, Taobao,
    Instagram, Telegram, Russian/Uzbek/English marketplaces).

    Extracts:
    1. Title & Category in Uzbek
    2. Price in foreign currency & converted to Uzbek So'm with 25-35% profit margin
    3. Sizes (尺码 / Размеры / Sizes / 均码 -> Standart)
    4. Colors translated into aesthetic Uzbek names with emojis (Pushti 🌸, Oq 🤍, etc.)

    Gracefully falls back on missing API key or network failure without throwing errors.
    """
    raw_key = (
        api_key
        or getattr(settings, "GEMINI_API_KEY", None)
        or os.environ.get("GEMINI_API_KEY")
    )
    resolved_key = raw_key.strip().strip("'\"") if raw_key else None
    if not resolved_key:
        logger.info("GEMINI_API_KEY is not configured; skipping vision OCR")
        return {
            "success": False,
            "error": "GEMINI_API_KEY is not configured",
            "source_price": 0,
            "retail_price": 0,
            "price": 0,
            "sizes": [],
            "colors": [],
            "title": "",
            "category": "kiyim",
        }

    # Load image bytes
    image_bytes: Optional[bytes] = None
    if isinstance(image_input, bytes):
        image_bytes = image_input
    elif hasattr(image_input, "read"):
        if hasattr(image_input, "seek"):
            image_input.seek(0)
        image_bytes = image_input.read()
    elif isinstance(image_input, (str, Path)):
        p = Path(image_input)
        if p.is_file():
            try:
                image_bytes = p.read_bytes()
            except Exception as e:
                logger.warning(f"Failed to read image file {p}: {e}")
                return {"success": False, "error": f"Failed to read image file: {e}"}
        elif isinstance(image_input, str):
            # Try decoding base64 if it's a data url or raw base64
            clean_str = image_input.strip()
            if clean_str.startswith("data:image/"):
                clean_str = clean_str.split(",", 1)[-1]
            try:
                image_bytes = base64.b64decode(clean_str)
            except Exception:
                image_bytes = None

    if not image_bytes or len(image_bytes) < 10:
        return {"success": False, "error": "Invalid or empty image data"}

    mime_type = _detect_image_mime(image_bytes)
    b64_data = base64.b64encode(image_bytes).decode("utf-8")

    primary_model = (
        model
        or getattr(settings, "GEMINI_VISION_MODEL", None)
        or DEFAULT_GEMINI_MODEL
    )
    models_to_try = [primary_model]
    if FALLBACK_GEMINI_MODEL not in models_to_try:
        models_to_try.append(FALLBACK_GEMINI_MODEL)

    prompt_text = (
        "You are an expert e-commerce product extraction AI for 'Moonlight Chinese Shop' "
        "(an aesthetic Korean/Chinese style boutique in Uzbekistan).\n"
        "Analyze this product screenshot (from Pinduoduo, 1688, Taobao, Poizon, Telegram, Instagram, "
        "Russian or English e-commerce).\n"
        "Read and extract all available product details:\n"
        "1. title: Aesthetic, clean product title in Uzbek (Latin script, e.g. 'Vintage Pushti Hoodie', "
        "'Koreyscha Elegant Ko'ylak', 'Zamonaviy Ayollar Sumkasi', 'Sport Krossovka').\n"
        "2. category: Latin slug strictly one of: 'hoodie', 'koylak', 'yubka', 'sumka', 'shoes', "
        "'jempir', 'shim', 'futbolka', 'kurtka', 'palto', 'wig', 'scarf', 'aksessuar', 'kosmetika'.\n"
        "3. raw_price: The primary active price number visible on the screenshot. "
        "If multiple prices appear (e.g. Pinduoduo 拼单价 vs 单买价 or coupon price 券后价), "
        "always choose the discounted active group-buy price (拼单价 / 券后价).\n"
        "4. currency: Currency symbol/code ('CNY' for ¥/元, 'USD' for $, 'RUB' for ₽/руб, 'UZS' for so'm/som). "
        "For Chinese marketplaces (Pinduoduo/1688/Taobao/Poizon), it is CNY.\n"
        "5. sizes: Array of available sizes (e.g. ['S', 'M', 'L', 'XL', '2XL'] or ['36', '37', '38'] "
        "or ['Standart'] if '均码', '一码', 'Free size', 'One size', or 'Стандарт'). "
        "Ignore Chinese weight annotations in parentheses (e.g., extract 'M' from 'M码 (建议90-105斤)').\n"
        "6. colors: Array of product colors translated into aesthetic Uzbek names with emojis "
        "(e.g. ['Pushti 🌸', 'Oq 🤍', 'Qora 🖤', 'Havorang 🩵', 'Bej 🤎', 'Yashil 💚', 'Qizil ❤️', "
        "'Sariq 💛', 'Binafsha 💜', 'Kulrang 🩶', 'Jigarrang 🤎', 'Krem rang 🍦']).\n"
        "7. cargo_rate: Optional cargo rate per 100g in UZS if explicitly shown on the screenshot, otherwise null.\n"
        "8. weight_grams: Optional item weight in grams if shown on the screenshot, otherwise null.\n\n"
        "Output ONLY a valid JSON object matching this schema:\n"
        "{\n"
        '  "title": "string",\n'
        '  "category": "string",\n'
        '  "raw_price": 0.0,\n'
        '  "currency": "CNY",\n'
        '  "sizes": ["string"],\n'
        '  "colors": ["string"],\n'
        '  "cargo_rate": null,\n'
        '  "weight_grams": null\n'
        "}"
    )

    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt_text},
                    {
                        "inline_data": {
                            "mime_type": mime_type,
                            "data": b64_data,
                        }
                    },
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.1,
            "response_mime_type": "application/json",
        },
    }

    last_error: Optional[str] = None

    async with httpx.AsyncClient(timeout=timeout) as client:
        for target_model in models_to_try:
            url = f"{GEMINI_ENDPOINT_TEMPLATE.format(model=target_model)}?key={resolved_key}"
            try:
                resp = await client.post(url, json=payload)
                if resp.status_code == 200:
                    resp_json = resp.json()
                    candidates = resp_json.get("candidates", [])
                    if not candidates:
                        last_error = "Gemini returned empty candidates"
                        continue

                    parts = candidates[0].get("content", {}).get("parts", [])
                    if not parts:
                        last_error = "Gemini returned empty parts"
                        continue

                    raw_text = parts[0].get("text", "").strip()
                    # Robust extraction of JSON object even if surrounded by commentary
                    m_json = re.search(r"\{.*\}", raw_text, re.DOTALL)
                    json_str = m_json.group(0) if m_json else raw_text

                    parsed_dict = json.loads(json_str)
                    return parse_vision_response(
                        parsed_dict,
                        yuan_rate=yuan_rate,
                        usd_rate=usd_rate,
                        rub_rate=rub_rate,
                    )
                else:
                    last_error = f"Gemini API ({target_model}) returned status {resp.status_code}: {resp.text[:200]}"
                    logger.warning(f"Gemini API ({target_model}) error: {last_error}")
            except httpx.TimeoutException:
                last_error = f"Gemini API ({target_model}) request timed out"
                logger.warning(last_error)
            except Exception as e:
                last_error = f"Gemini API ({target_model}) call failed: {e}"
                logger.warning(last_error)

    return {
        "success": False,
        "error": last_error or "Vision extraction failed",
        "source_price": 0,
        "retail_price": 0,
        "price": 0,
        "sizes": [],
        "colors": [],
        "title": "",
        "category": "kiyim",
    }
