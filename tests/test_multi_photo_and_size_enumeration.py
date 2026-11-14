import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy import select

from api.services.formatters import format_sizes_display, parse_sizes, build_channel_caption
from bot.services.channel_post import post_product_to_channel
from db.models import Product, Setting, Category


def test_format_sizes_display_four_sizes_explicit_enumeration():
    """
    Addresses the user complaint:
    'rasmda 4 xil razmer ko'rsatilgan u esa atiga 2 ta razmerni yozgan'
    Ensure 4 sizes (e.g. S, M, L, XL) are explicitly enumerated as 'S, M, L, XL'
    rather than compressed into 'S-XL' which looks like only 2 sizes.
    """
    assert format_sizes_display(["S", "M", "L", "XL"]) == "S, M, L, XL"
    assert format_sizes_display(["S", "M", "L"]) == "S, M, L"
    assert format_sizes_display(["S", "M"]) == "S, M"
    assert format_sizes_display(["M", "L", "XL"]) == "M, L, XL"
    assert format_sizes_display(["36", "37", "38", "39"]) == "36, 37, 38, 39"

    # Continuous ranges with 5 or more sizes are abbreviated
    assert format_sizes_display(["S", "M", "L", "XL", "2XL"]) == "S-2XL"
    assert format_sizes_display(["36", "37", "38", "39", "40"]) == "36-40"

    # Enumerate all when requested
    assert format_sizes_display(["S", "M", "L", "XL", "2XL"], enumerate_all=True) == "S, M, L, XL, 2XL"

    # Discontinuous sizes
    assert format_sizes_display(["S", "XL"]) == "S, XL"
    assert format_sizes_display(["S", "L", "2XL"]) == "S, L, 2XL"
    assert format_sizes_display(["Standart"]) == "Standart"
    assert format_sizes_display([]) == ""


def test_parse_sizes_chinese_spec_with_weight_brackets():
    """
    Pinduoduo/1688 spec table with weight notes e.g.:
    S 【80-95斤】, M 【95-110斤】, L 【110-120斤】, XL 【120-135斤】
    """
    text = "S 【80-95斤】, M 【95-110斤】, L 【110-120斤】, XL 【120-135斤】"
    parsed = parse_sizes(text)
    assert parsed == ["S", "M", "L", "XL"]

    # With spaces inside brackets
    text2 = "S 【80-95 斤】, M 【95-110 斤】"
    parsed2 = parse_sizes(text2)
    assert parsed2 == ["S", "M"]

    # With kg notation
    text3 = "M (45-55kg), L (55-65kg)"
    parsed3 = parse_sizes(text3)
    assert parsed3 == ["M", "L"]


def test_channel_caption_displays_all_four_sizes():
    """Verify channel caption displays all 4 sizes explicitly."""
    caption = build_channel_caption(
        category_slug="jempir",
        price=120000,
        cargo_rate=10000,
        contact_username="MOONLIGHT_ADMINNN",
        title="Oversize Issiq Jempir",
        sizes=["S", "M", "L", "XL"],
        adapted_style=True,
    )
    assert "Razmer:</b> S, M, L, XL" in caption
    assert "S-XL" not in caption


@pytest.mark.asyncio
async def test_post_product_with_multiple_photos_sends_album(test_db_session):
    """
    Verifies the user complaint:
    'va atigi 1 dona rasmni yuborgan man bo'lsam mahsulotni 3 ta rasmini yuborgan edim'
    When a product has 3 model photos, post_product_to_channel MUST send all 3 photos
    as an album via send_media_group, with caption and webapp shopping link attached.
    """
    async with test_db_session() as session:
        cat = Category(slug="cardigan", name="Kardigan", emoji="🧥", sort_order=1)
        session.add(cat)
        prod = Product(
            id=4444,
            title="Issiq kardigan",
            price=135000,
            source_price=95000,
            category="cardigan",
            photos=["cardigan_brown.jpg", "cardigan_grey.jpg", "cardigan_cream.jpg"],
            sizes=["S", "M", "L", "XL"],
            colors=["Jigarrang", "Kulrang", "Krem"],
        )
        session.add(prod)
        res_ch = await session.execute(select(Setting).where(Setting.key == "channel_id"))
        ch = res_ch.scalars().first()
        if ch:
            ch.value = "@moonlight_chinese_shop"
        else:
            session.add(Setting(key="channel_id", value="@moonlight_chinese_shop"))
        await session.commit()

    captured_media_group = None
    captured_chat_id = None

    async def fake_send_media_group(chat_id, media, **kwargs):
        nonlocal captured_media_group, captured_chat_id
        captured_chat_id = chat_id
        captured_media_group = media
        m1 = MagicMock()
        m1.message_id = 9001
        m2 = MagicMock()
        m2.message_id = 9002
        m3 = MagicMock()
        m3.message_id = 9003
        return [m1, m2, m3]

    with patch("bot.services.channel_post.async_session_factory", test_db_session), \
         patch("bot.services.channel_post.bot") as mock_bot:
        mock_bot.get_me = AsyncMock(return_value=MagicMock(username="moonlight_chinese_bot"))
        mock_bot.send_media_group = AsyncMock(side_effect=fake_send_media_group)
        mock_bot.send_photo = AsyncMock()

        res = await post_product_to_channel(prod)
        assert res["success"] is True
        assert res["channel_message_id"] == 9001

        # send_photo should NOT have been called because it's an album
        assert mock_bot.send_photo.call_count == 0
        assert mock_bot.send_media_group.call_count == 1
        assert captured_chat_id == "@moonlight_chinese_shop"

        # Verify all 3 photos were included in the media group!
        assert len(captured_media_group) == 3
        # Primary photo has the caption
        first_item = captured_media_group[0]
        assert first_item.caption is not None
        assert "Razmer:</b> S, M, L, XL" in first_item.caption
        assert "Do'konda xarid qilish" in first_item.caption
        assert "https://t.me/moonlight_chinese_bot?start=product_4444" in first_item.caption

        # Subsequent photos have no caption (so they don't repeat)
        assert captured_media_group[1].caption is None
        assert captured_media_group[2].caption is None

    # Verify channel_message_id was saved to the database
    async with test_db_session() as session:
        saved_prod = await session.get(Product, 4444)
        assert saved_prod.channel_message_id == 9001


@pytest.mark.asyncio
async def test_post_product_filters_spec_screenshot_and_sends_remaining_album(test_db_session):
    """
    When user sends 3 product model photos + 1 spec screenshot,
    the spec screenshot is filtered out, and the 3 clean model photos are sent as an album.
    """
    async with test_db_session() as session:
        prod = Product(
            id=5555,
            title="Qalin Sviter",
            price=110000,
            source_price=80000,
            category="jempir",
            photos=[
                "model_photo1.jpg",
                "model_photo2.jpg",
                "model_photo3.jpg",
                "spec_screenshot_size_table.jpg",
            ],
            sizes=["S", "M", "L", "XL"],
        )
        session.add(prod)
        await session.commit()

    captured_media_group = None

    async def fake_send_media_group(chat_id, media, **kwargs):
        nonlocal captured_media_group
        captured_media_group = media
        m = MagicMock()
        m.message_id = 9050
        return [m]

    with patch("bot.services.channel_post.async_session_factory", test_db_session), \
         patch("bot.services.channel_post.bot") as mock_bot:
        mock_bot.get_me = AsyncMock(return_value=MagicMock(username="moonlight_chinese_bot"))
        mock_bot.send_media_group = AsyncMock(side_effect=fake_send_media_group)
        mock_bot.send_photo = AsyncMock()

        res = await post_product_to_channel(prod)
        assert res["success"] is True

        # Exactly 3 clean photos sent, spec screenshot omitted!
        assert len(captured_media_group) == 3
        media_names = [getattr(item.media, "path", str(item.media)) for item in captured_media_group]
        assert not any("spec" in str(name).lower() for name in media_names)


@pytest.mark.asyncio
async def test_post_product_album_fallback_when_premium_fails(test_db_session):
    """
    Verify album send_media_group retry fallback when premium custom emojis are rejected.
    """
    async with test_db_session() as session:
        prod = Product(
            id=6666,
            title="Test Multi Photo Item",
            price=99000,
            category="dress",
            photos=["dress_1.jpg", "dress_2.jpg"],
            sizes=["S", "M", "L"],
        )
        session.add(prod)
        await session.commit()

    attempt_count = 0

    async def fake_send_media_group(chat_id, media, **kwargs):
        nonlocal attempt_count
        attempt_count += 1
        if attempt_count == 1:
            raise RuntimeError("Bad Request: can't use custom emoji")
        m = MagicMock()
        m.message_id = 9100
        return [m]

    with patch("bot.services.channel_post.async_session_factory", test_db_session), \
         patch("bot.services.channel_post.bot") as mock_bot:
        mock_bot.get_me = AsyncMock(return_value=MagicMock(username="moonlight_chinese_bot"))
        mock_bot.send_media_group = AsyncMock(side_effect=fake_send_media_group)

        res = await post_product_to_channel(prod)
        assert res["success"] is True
        assert res["channel_message_id"] == 9100
        assert attempt_count == 2
