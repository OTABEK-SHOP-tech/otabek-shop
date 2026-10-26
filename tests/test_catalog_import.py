from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from bekstyle.catalog_import import CostInputs, sale_price, validate_manifest


NOW = datetime(2026, 10, 26, 12, tzinfo=timezone.utc)


def manifest(**changes):
    value = {
        "products": [{
            "source_url": "https://mobile.yangkeduo.com/goods.html?goods_id=123",
            "source_product_id": "123",
            "verified": True,
            "checked_at": "2026-10-26T10:00:00+00:00",
            "title": "Erkaklar futbolkasi",
            "category": "Futbolkalar",
            "photos": ["https://img.pddpic.com/product/a.jpg"],
            "costs": {"yuan_rate": 1850, "china_shipping_cny": 2, "intermediary_fee_som": 3000, "other_costs_som": 0},
            "target_profit_som": 30000,
            "variants": [{"sku_id": "sku-1", "color": "Qora", "size": "L", "cost_cny": "40", "in_stock": True}],
        }]
    }
    value["products"][0].update(changes)
    return value


def test_exact_decimal_price_and_margin_boundary():
    plans = validate_manifest(manifest(), now=NOW)
    variant = plans[0].variants[0]
    assert variant.sale_price_som == 111000
    assert variant.sale_price_som - round((Decimal("40") + Decimal("2")) * 1850) - 3000 >= 30000


def test_all_explicit_zero_costs_are_allowed():
    costs = CostInputs(Decimal("1850"), Decimal(0), Decimal(0), Decimal(0))
    assert sale_price(Decimal("1.001"), costs, 5000) == 7000


@pytest.mark.parametrize("url", ["http://mobile.yangkeduo.com/goods/1", "https://evilpinduoduo.com/goods/1", "https://pinduoduo.com.evil.test/goods/1"])
def test_untrusted_source_url_rejected(url):
    with pytest.raises(ValueError):
        validate_manifest(manifest(source_url=url), now=NOW)


def test_stale_future_and_timezone_less_records_rejected():
    for checked_at in ["2026-10-25T11:00:00+00:00", "2026-10-26T13:00:00+00:00", "2026-10-26T10:00:00"]:
        with pytest.raises(ValueError):
            validate_manifest(manifest(checked_at=checked_at), now=NOW)


def test_missing_costs_and_unverified_variant_rejected():
    with pytest.raises(ValueError):
        validate_manifest(manifest(costs=None), now=NOW)
    with pytest.raises(ValueError):
        validate_manifest(manifest(variants=[{"sku_id": "sku-1", "color": "Qora", "size": "L"}]), now=NOW)


def test_duplicate_identity_and_sku_rejected():
    doc = manifest()
    doc["products"].append(doc["products"][0].copy())
    with pytest.raises(ValueError):
        validate_manifest(doc, now=NOW)
    doc = manifest()
    doc["products"][0]["variants"].append({"sku_id": "sku-1", "color": "Oq", "size": "M", "cost_cny": 30, "in_stock": True})
    with pytest.raises(ValueError):
        validate_manifest(doc, now=NOW)


def test_invalid_target_and_photo_cdn_rejected():
    with pytest.raises(ValueError):
        validate_manifest(manifest(target_profit_som=15000), now=NOW)
    with pytest.raises(ValueError):
        validate_manifest(manifest(photos=["https://images.unsplash.com/photo.jpg"]), now=NOW)


def test_verified_stock_and_positive_cost_rate_are_required():
    with pytest.raises(ValueError):
        validate_manifest(manifest(verified=False), now=NOW)
    with pytest.raises(ValueError):
        validate_manifest(manifest(costs={"yuan_rate": 0, "china_shipping_cny": 0, "intermediary_fee_som": 0, "other_costs_som": 0}), now=NOW)
    with pytest.raises(ValueError):
        validate_manifest(manifest(variants=[{"sku_id": "sku-1", "color": "Qora", "size": "L", "cost_cny": 0, "in_stock": True}]), now=NOW)
    with pytest.raises(ValueError):
        validate_manifest(manifest(variants=[{"sku_id": "sku-1", "color": "Qora", "size": "L", "cost_cny": 40}]), now=NOW)


def test_url_userinfo_port_fragment_and_canonical_pid_rejected():
    for url in [
        "https://user:pass@mobile.yangkeduo.com/goods/1",
        "https://mobile.yangkeduo.com:443/goods/1",
        "https://mobile.yangkeduo.com/goods/1#frag",
    ]:
        with pytest.raises(ValueError):
            validate_manifest(manifest(source_url=url), now=NOW)
    doc = manifest()
    second = manifest(source_url="https://m.pinduoduo.com/goods.html?goods_id=123")["products"][0]
    doc["products"].append(second)
    with pytest.raises(ValueError):
        validate_manifest(doc, now=NOW)


def test_optional_variant_axes_require_explicit_null_and_cannot_mix():
    plan = validate_manifest(manifest(variants=[{"sku_id": "sku-1", "color": None, "size": None, "cost_cny": 40, "in_stock": True}]), now=NOW)
    assert plan[0].variants[0].color is None and plan[0].variants[0].size is None
    with pytest.raises(ValueError):
        validate_manifest(manifest(variants=[{"sku_id": "sku-1", "size": "L", "cost_cny": 40, "in_stock": True}]), now=NOW)
    with pytest.raises(ValueError):
        validate_manifest(manifest(variants=[{"sku_id": "sku-1", "color": None, "size": "L", "cost_cny": 40, "in_stock": True}, {"sku_id": "sku-2", "color": "Qora", "size": "M", "cost_cny": 40, "in_stock": True}]), now=NOW)
