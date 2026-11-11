import pytest
from api.services.formatters import mask_customer_name, format_cargo_stage, CARGO_STAGE_NAMES

def test_mask_customer_name():
    assert mask_customer_name("Otabek") == "O****k"
    assert mask_customer_name("Gulmira") == "G*****a"
    assert mask_customer_name("Al") == "A***"
    assert mask_customer_name("X") == "X***"
    assert mask_customer_name("") == "M***z"

def test_cargo_stages():
    assert len(CARGO_STAGE_NAMES) == 5
    assert format_cargo_stage("china_warehouse") == "🇨🇳 Xitoy omborida"
    assert format_cargo_stage("in_transit_border") == "🚛 Xorgos chegarasida"
    assert format_cargo_stage("customs_clearance") == "🛃 Bojxona nazoratida"
    assert format_cargo_stage("tashkent_hub") == "📍 Toshkent omborida"
    assert format_cargo_stage("delivering") == "🛍 Yetkazilmoqda"

def test_cashback_economics():
    order_total = 250000
    earned = int(order_total * 0.02)
    assert earned == 5000

    new_order_subtotal = 100000
    user_balance = 30000
    max_usable = min(user_balance, int(new_order_subtotal * 0.20))
    assert max_usable == 20000
