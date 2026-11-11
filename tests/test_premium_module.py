import pytest
from bot.services.premium_emojis import (
    upgrade_to_premium_emojis,
    strip_custom_emojis,
    make_premium_button,
    TG_MOON,
    TG_SAKURA,
    TG_MONEY,
    TG_CARGO,
    PREMIUM_BTN_BAG_ID,
)


def test_upgrade_to_premium_emojis():
    raw_text = "🌙 Moonlight Shop 🌸\n💰 Narxi: 45.000 so'm\n📦 Kargo: 12.000 so'm"
    upgraded = upgrade_to_premium_emojis(raw_text)

    assert TG_MOON in upgraded
    assert TG_SAKURA in upgraded
    assert TG_MONEY in upgraded
    assert TG_CARGO in upgraded
    assert '<tg-emoji emoji-id="5429099589997184246">' in upgraded


def test_strip_custom_emojis():
    raw_text = "🌙 Moonlight Shop 🌸"
    upgraded = upgrade_to_premium_emojis(raw_text)
    stripped = strip_custom_emojis(upgraded)

    assert "<tg-emoji" not in stripped
    assert "🌙" in stripped
    assert "🌸" in stripped


def test_make_premium_button():
    btn = make_premium_button("🛍️ Do'konda ko'rish", url="https://t.me/moonlight_chinese_bot")
    assert btn.text == "Do'konda ko'rish"
    assert btn.icon_custom_emoji_id == PREMIUM_BTN_BAG_ID
    assert btn.style == "primary"
    assert btn.url == "https://t.me/moonlight_chinese_bot"
