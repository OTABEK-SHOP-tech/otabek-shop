from datetime import UTC, datetime

from bekstyle import texts as t
from bekstyle.services import (
    PriceInput,
    can_move,
    margin_som,
    parse_category_input,
    parse_list,
    parse_price_input,
    round_up_thousand,
    sale_price_from_yuan,
    validate_setting,
)


def test_yuan_price_gets_markup_and_rounds_up_to_thousand() -> None:
    # 79 * 1800 * 1.40 = 199 080 -> 200 000
    assert parse_price_input("79¥", 1800, 40) == PriceInput(200_000, 79.0)
    assert parse_price_input("79 yuan", 1800, 40) == PriceInput(200_000, 79.0)
    assert parse_price_input("39,9 Y", 1800, 0) == PriceInput(72_000, 39.9)


def test_som_price_is_taken_as_is() -> None:
    assert parse_price_input("189000", 1800, 40) == PriceInput(189_000, None)
    assert parse_price_input("189 000 so'm", 1800, 40) == PriceInput(189_000, None)
    assert parse_price_input("1.250.000", 1800, 40) == PriceInput(1_250_000, None)


def test_bad_or_suspicious_prices_are_rejected() -> None:
    assert parse_price_input("79", 1800, 40) is None  # forgot ¥
    assert parse_price_input("abc", 1800, 40) is None
    assert parse_price_input("0¥", 1800, 40) is None
    assert parse_price_input("²³⁴⁵", 1800, 40) is None  # unicode digits must not crash int()


def test_rounding_and_margin() -> None:
    assert round_up_thousand(199_000.0000001) == 199_000  # float noise does not add 1000
    assert round_up_thousand(199_001) == 200_000
    assert sale_price_from_yuan(100, 1800, 50) == 270_000
    assert margin_som(200_000, 79, 1800) == 57_800
    assert margin_som(200_000, None, 1800) is None


def test_lists_settings_and_categories() -> None:
    assert parse_list(" Qora , Oq,,Yashil ") == ["Qora", "Oq", "Yashil"]
    assert validate_setting("contact_username", "@bekstyle_admin") == "bekstyle_admin"
    assert validate_setting("contact_username", "@ab") is None
    assert validate_setting("yuan_rate", "1800") == "1800"
    assert validate_setting("yuan_rate", "18") is None
    assert validate_setting("markup_percent", "600") is None
    assert validate_setting("unknown", "x") is None
    assert parse_category_input("🩳 Shortilar") == ("🩳", "Shortilar")
    assert parse_category_input("Shortilar") == ("▫️", "Shortilar")
    assert parse_category_input("🩳 x") is None


def test_status_flow() -> None:
    assert t.next_status("pending_payment") == "payment_review"
    assert t.next_status("done") is None
    assert can_move("new", "accepted")
    assert not can_move("new", "shipping")  # no skipping steps
    assert can_move("shipping", "cancelled")
    assert not can_move("done", "cancelled")
    assert not can_move("cancelled", "accepted")


def test_brand_texts() -> None:
    assert t.format_price(1_250_000) == "1 250 000 so'm"
    assert t.hashtag("Hudi va svitshotlar") == "#hudi_va_svitshotlar"
    long_caption = t.channel_caption(
        "A" * 120, 189_000, "Futbolkalar", ["Qora"] * 12, ["XL"] * 12, "x" * 2000, "15 kun"
    )
    assert len(long_caption) <= t.CAPTION_LIMIT
    caption = t.product_caption("<b>hack</b>", 189_000, ["Qora"], ["L"], "", "15–25 kun", True)
    assert "&lt;b&gt;hack" in caption and "189 000 so'm" in caption
    naive_utc = datetime(2026, 10, 25, 16, 40)  # noqa: DTZ001 - SQLite hands back naive UTC
    assert t.format_dt(naive_utc) == "25.10.2026 21:40"
    assert t.format_dt(naive_utc.replace(tzinfo=UTC)) == "25.10.2026 21:40"
