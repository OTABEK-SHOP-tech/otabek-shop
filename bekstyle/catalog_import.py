"""Pure validation and pricing for verified Pinduoduo catalogue batches.

This module intentionally performs no network, Telegram, or database I/O.  A
record is publishable only when its source, freshness, photos, variants, and
all cost inputs are explicit.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_CEILING
from math import isfinite
from urllib.parse import urlparse


OFFICIAL_HOSTS = {"mobile.yangkeduo.com", "m.pinduoduo.com", "yangkeduo.com", "pinduoduo.com"}
PHOTO_HOSTS = {"pddpic.com", "yangkeduo.com"}
TARGET_PROFITS = {5000, 10000, 30000}
MAX_AGE = timedelta(hours=24)


@dataclass(frozen=True)
class CostInputs:
    yuan_rate: Decimal
    china_shipping_cny: Decimal
    intermediary_fee_som: Decimal
    other_costs_som: Decimal


@dataclass(frozen=True)
class VariantPlan:
    sku_id: str
    color: str | None
    size: str | None
    cost_cny: Decimal
    sale_price_som: int
    target_profit_som: int
    in_stock: bool


@dataclass(frozen=True)
class ProductPlan:
    source_url: str
    source_product_id: str
    title: str
    category: str
    photos: tuple[str, ...]
    variants: tuple[VariantPlan, ...]
    checked_at: datetime
    costs: CostInputs


def _decimal(value: object, field: str) -> Decimal:
    if isinstance(value, bool) or value is None:
        raise ValueError(f"{field} must be an explicit non-negative number")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise ValueError(f"{field} is not a valid decimal") from None
    if not result.is_finite() or result < 0:
        raise ValueError(f"{field} must be finite and non-negative")
    return result


def _text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} is required")
    return value.strip()


def _optional_text(value: object, field: str) -> str | None:
    if value is None:
        return None
    return _text(value, field)


def _official_url(value: object) -> str:
    raw = _text(value, "source_url")
    parsed = urlparse(raw)
    host = (parsed.hostname or "").lower().rstrip(".")
    if parsed.scheme != "https" or not parsed.netloc or not parsed.path or parsed.username or parsed.password or parsed.port or parsed.fragment:
        raise ValueError("source_url must be an HTTPS Pinduoduo URL")
    if host not in OFFICIAL_HOSTS and not any(host.endswith("." + h) for h in OFFICIAL_HOSTS):
        raise ValueError("source_url host is not an official Pinduoduo domain")
    return raw


def _photo(value: object) -> str:
    raw = _text(value, "photo")
    parsed = urlparse(raw)
    host = (parsed.hostname or "").lower().rstrip(".")
    if parsed.scheme != "https" or not parsed.path or not (
        host in PHOTO_HOSTS or any(host.endswith("." + h) for h in PHOTO_HOSTS)
    ):
        raise ValueError("photos must be HTTPS official Pinduoduo CDN URLs")
    return raw


def _checked_at(value: object, now: datetime) -> datetime:
    raw = _text(value, "checked_at")
    try:
        checked = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        raise ValueError("checked_at must be ISO-8601") from None
    if checked.tzinfo is None:
        raise ValueError("checked_at must include a timezone")
    checked = checked.astimezone(timezone.utc)
    if checked > now + timedelta(seconds=30) or now - checked > MAX_AGE:
        raise ValueError("checked_at must be recent (within 24 hours) and not future-dated")
    return checked


def _costs(raw: object) -> CostInputs:
    if not isinstance(raw, dict):
        raise ValueError("costs must explicitly provide all cost fields")
    return CostInputs(
        _decimal(raw.get("yuan_rate"), "yuan_rate"),
        _decimal(raw.get("china_shipping_cny"), "china_shipping_cny"),
        _decimal(raw.get("intermediary_fee_som"), "intermediary_fee_som"),
        _decimal(raw.get("other_costs_som"), "other_costs_som"),
    )


def sale_price(cost_cny: Decimal, costs: CostInputs, target_profit_som: int) -> int:
    """Round up to 1,000 so margin includes every supplied non-cargo cost."""
    base = (cost_cny + costs.china_shipping_cny) * costs.yuan_rate
    total_cost = base + costs.intermediary_fee_som + costs.other_costs_som
    raw = total_cost + Decimal(target_profit_som)
    return int((raw / Decimal(1000)).to_integral_value(rounding=ROUND_CEILING) * 1000)


def validate_manifest(document: object, *, now: datetime | None = None) -> tuple[ProductPlan, ...]:
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    if not isinstance(document, dict) or not isinstance(document.get("products"), list) or not document["products"]:
        raise ValueError("document.products must be a non-empty array")
    plans: list[ProductPlan] = []
    identities: set[str] = set()
    sku_ids: set[str] = set()
    for item in document["products"]:
        if not isinstance(item, dict):
            raise ValueError("each product must be an object")
        url = _official_url(item.get("source_url"))
        pid = _text(item.get("source_product_id"), "source_product_id")
        if len(pid) > 128:
            raise ValueError("source_product_id is too long")
        if pid in identities:
            raise ValueError("duplicate source product identity")
        identities.add(pid)
        checked_at = _checked_at(item.get("checked_at"), now)
        if item.get("verified") is not True:
            raise ValueError("product must be explicitly verified")
        title, category = _text(item.get("title"), "title"), _text(item.get("category"), "category")
        if len(title) > 100 or len(category) > 64:
            raise ValueError("title or category is too long")
        photos_raw = item.get("photos")
        if not isinstance(photos_raw, list) or not photos_raw:
            raise ValueError("photos must be a non-empty array")
        if len(photos_raw) > 10:
            raise ValueError("photos must contain at most 10 items")
        photos = tuple(_photo(p) for p in photos_raw)
        costs = _costs(item.get("costs"))
        if costs.yuan_rate <= 0:
            raise ValueError("yuan_rate must be greater than zero")
        target = item.get("target_profit_som")
        if isinstance(target, bool) or not isinstance(target, int) or target not in TARGET_PROFITS:
            raise ValueError("target_profit_som must be exactly 5000, 10000, or 30000")
        variants_raw = item.get("variants")
        if not isinstance(variants_raw, list) or not variants_raw:
            raise ValueError("variants must be a non-empty array")
        variants: list[VariantPlan] = []
        for variant in variants_raw:
            if not isinstance(variant, dict):
                raise ValueError("each variant must be an object")
            if "color" not in variant or "size" not in variant:
                raise ValueError("each variant must explicitly include color and size (null allowed)")
            sku = _text(variant.get("sku_id"), "sku_id")
            color, size = _optional_text(variant.get("color"), "color"), _optional_text(variant.get("size"), "size")
            if any(value is not None and len(value) > limit for value, limit in ((sku, 128), (color, 64), (size, 32))):
                raise ValueError("variant field is too long")
            if not isinstance(variant.get("in_stock"), bool):
                raise ValueError("variant in_stock must be explicitly true or false")
            if sku in sku_ids:
                raise ValueError("duplicate SKU id")
            sku_ids.add(sku)
            cost = _decimal(variant.get("cost_cny"), "cost_cny")
            if cost <= 0:
                raise ValueError("cost_cny must be greater than zero")
            price = sale_price(cost, costs, target)
            variants.append(VariantPlan(sku, color, size, cost, price, target, variant["in_stock"]))
        for axis, values in (("color", [v.color for v in variants]), ("size", [v.size for v in variants])):
            if any(v is None for v in values) and any(v is not None for v in values):
                raise ValueError(f"{axis} cannot mix null and string values within one product")
        plans.append(ProductPlan(url, pid, title, category, photos, tuple(variants), checked_at, costs))
    return tuple(plans)
