"""
Bot service wrapper for Vision OCR extraction.
Re-exports api.services.vision_ocr functions for convenient bot handler imports.
"""

from api.services.vision_ocr import (
    COLOR_MAP,
    CATEGORY_KEYWORDS,
    ONE_SIZE_CATEGORIES,
    convert_currency_to_uzs,
    normalize_color,
    normalize_colors,
    normalize_sizes,
    normalize_category,
    parse_vision_response,
    extract_product_from_image,
)

__all__ = [
    "COLOR_MAP",
    "CATEGORY_KEYWORDS",
    "ONE_SIZE_CATEGORIES",
    "convert_currency_to_uzs",
    "normalize_color",
    "normalize_colors",
    "normalize_sizes",
    "normalize_category",
    "parse_vision_response",
    "extract_product_from_image",
]
