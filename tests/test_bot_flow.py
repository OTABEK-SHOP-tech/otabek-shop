"""End-to-end: real dispatcher, handlers and DB; only the Telegram transport is faked."""

import asyncio
import itertools
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from typing import Any

import pytest
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.base import BaseSession
from aiogram.enums import ParseMode
from aiogram.methods import AnswerCallbackQuery, TelegramMethod
from aiogram.types import CallbackQuery, Chat, Message, MessageId, PhotoSize, Update, User
from sqlalchemy import select

from bekstyle import texts as t
from bekstyle.__main__ import build_dispatcher
from bekstyle.config import settings
from bekstyle.db import Admin, CartItem, Category, Order, Product, async_session
from bekstyle.services import sale_price_from_yuan

BOT_USER = User(id=42, is_bot=True, first_name="BEK STYLE", username="bekstyle_test_bot")
OWNER = User(id=111, is_bot=False, first_name="Bek", username="bek_owner")
CUSTOMER = User(id=222, is_bot=False, first_name="Aziz", username="aziz")
# aiogram routers are module singletons: one dispatcher per process, shared by the tests below.
DP = build_dispatcher()


class FakeTelegram(BaseSession):
    def __init__(self) -> None:
        super().__init__()
        self.calls: list[TelegramMethod[Any]] = []
        self._ids = itertools.count(1000)

    async def close(self) -> None:
        return None

    async def stream_content(self, *args: Any, **kwargs: Any) -> AsyncGenerator[bytes, None]:
        raise NotImplementedError
        yield b""

    async def make_request(self, bot: Bot, method: TelegramMethod[Any], timeout: int | None = None) -> Any:
        self.calls.append(method)
        name = type(method).__name__
        if name == "GetMe":
            return BOT_USER
        if name == "SendMediaGroup":
            return [self._message(method) for _ in method.media]
        if name == "CopyMessage":
            return MessageId(message_id=next(self._ids))
        if "Message" in str(method.__returning__):
            return self._message(method)
        return True

    def _message(self, method: TelegramMethod[Any]) -> Message:
        chat_id = int(getattr(method, "chat_id", None) or 0)
        text = getattr(method, "text", None) or getattr(method, "caption", None) or ""
        return Message(
            message_id=next(self._ids),
            date=datetime.now(UTC),
            chat=Chat(id=chat_id, type="private"),
            text=text,
        )

    def texts_to(self, chat_id: int) -> list[str]:
        out: list[str] = []
        for call in self.calls:
            if getattr(call, "chat_id", None) == chat_id:
                out.append(str(getattr(call, "text", None) or getattr(call, "caption", None) or ""))
        return out

    def alerts(self) -> list[str]:
        return [str(c.text) for c in self.calls if isinstance(c, AnswerCallbackQuery) and c.show_alert]


_update_ids = itertools.count(1)


def _now() -> datetime:
    return datetime.now(UTC)


def text_update(user: User, text: str) -> Update:
    chat = Chat(id=user.id, type="private")
    return Update(
        update_id=next(_update_ids),
        message=Message(message_id=next(_update_ids), date=_now(), chat=chat, from_user=user, text=text),
    )


def photo_update(user: User, file_id: str, group: str | None = None) -> Update:
    chat = Chat(id=user.id, type="private")
    photo = [PhotoSize(file_id=file_id, file_unique_id=f"u-{file_id}", width=800, height=800)]
    message = Message(
        message_id=next(_update_ids), date=_now(), chat=chat, from_user=user, photo=photo, media_group_id=group
    )
    return Update(update_id=next(_update_ids), message=message)


def callback_update(user: User, data: str, photo: bool = False) -> Update:
    chat = Chat(id=user.id, type="private")
    if photo:
        bot_message = Message(
            message_id=next(_update_ids),
            date=_now(),
            chat=chat,
            from_user=BOT_USER,
            photo=[PhotoSize(file_id="card", file_unique_id="card", width=800, height=800)],
            caption="card",
        )
    else:
        bot_message = Message(message_id=next(_update_ids), date=_now(), chat=chat, from_user=BOT_USER, text="menu")
    query = CallbackQuery(id=str(next(_update_ids)), from_user=user, chat_instance="ci", message=bot_message, data=data)
    return Update(update_id=next(_update_ids), callback_query=query)


@pytest.mark.usefixtures("db")
async def test_owner_adds_product_customer_orders_admin_moves_status() -> None:
    tg = FakeTelegram()
    bot = Bot("42:TEST-TOKEN", session=tg, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = DP

    async def feed(update: Update) -> None:
        await dp.feed_update(bot, update)

    # 1. Owner claims the shop with the secret link.
    await feed(text_update(OWNER, f"/start claim_{settings.OWNER_SETUP_CODE}"))
    assert any("sizniki" in text for text in tg.texts_to(OWNER.id))

    # A customer cannot open admin screens.
    await feed(callback_update(CUSTOMER, "ap:add"))
    assert not any("Yangi mahsulot" in text for text in tg.texts_to(CUSTOMER.id))

    # 2. Owner adds a product: album photos arrive concurrently, none may be lost.
    await feed(callback_update(OWNER, "ap:add"))
    await asyncio.gather(*(feed(photo_update(OWNER, f"file-{i}", group="album-1")) for i in range(3)))
    await feed(text_update(OWNER, t.BTN_DONE_PHOTOS))
    await feed(text_update(OWNER, "Oversize futbolka «Essential»"))
    async with async_session() as session:
        category_id = await session.scalar(select(Category.id).order_by(Category.sort_order).limit(1))
    await feed(callback_update(OWNER, f"wcat:{category_id}"))
    await feed(text_update(OWNER, "79¥"))
    await feed(text_update(OWNER, "Qora, Oq"))
    await feed(text_update(OWNER, "M, L, XL"))
    await feed(text_update(OWNER, t.BTN_SKIP))
    await feed(callback_update(OWNER, "wsave", photo=True))

    async with async_session() as session:
        product = await session.scalar(select(Product))
    assert product is not None
    assert sorted(product.photos) == ["file-0", "file-1", "file-2"]
    assert product.price == sale_price_from_yuan(79, 1800, 40)
    assert product.cost_cny == 79
    assert (product.colors, product.sizes) == (["Qora", "Oq"], ["M", "L", "XL"])

    # 3. Customer: greeting, catalog, colour -> size -> cart, checkout.
    await feed(text_update(CUSTOMER, "/start"))
    assert any(t.BRAND in text for text in tg.texts_to(CUSTOMER.id))
    await feed(text_update(CUSTOMER, t.BTN_CATALOG))
    assert any("Katalog" in text for text in tg.texts_to(CUSTOMER.id))
    for step in ("x:x", "1:x", "1:2"):  # Oq, XL
        await feed(callback_update(CUSTOMER, f"b:{product.id}:{category_id}:{step}", photo=True))
    async with async_session() as session:
        cart = (await session.scalars(select(CartItem).where(CartItem.user_id == CUSTOMER.id))).all()
    assert [(c.color, c.size, c.qty) for c in cart] == [("Oq", "XL", 1)]

    await feed(callback_update(CUSTOMER, "checkout"))
    await feed(text_update(CUSTOMER, "+998 90 123 45 67"))
    await feed(text_update(CUSTOMER, "Toshkent, Chilonzor, 9-kvartal"))
    await feed(callback_update(CUSTOMER, "co:yes"))

    async with async_session() as session:
        order = await session.scalar(select(Order))
        cart_left = await session.scalar(select(CartItem.id))
    assert order is not None and cart_left is None
    assert (order.status, order.total, order.phone) == ("new", product.price, "+998901234567")
    assert any("Yangi buyurtma" in text for text in tg.texts_to(OWNER.id))

    # 4. Admin moves the order on; the customer is told. A repeated click changes nothing.
    await feed(callback_update(OWNER, f"os:{order.id}:accepted"))
    await feed(callback_update(OWNER, f"os:{order.id}:accepted"))
    async with async_session() as session:
        refreshed = await session.get(Order, order.id)
        owner_row = await session.get(Admin, OWNER.id)
    assert refreshed is not None and refreshed.status == "accepted"
    assert owner_row is not None and owner_row.role == "owner"
    assert sum("Tasdiqlandi" in text for text in tg.texts_to(CUSTOMER.id)) == 1
    assert any("allaqachon" in alert for alert in tg.alerts())


@pytest.mark.usefixtures("db")
async def test_channel_post_deep_link_and_broadcast() -> None:
    from bekstyle.db import User as DbUser
    from bekstyle.db import set_setting
    from bekstyle.handlers import admin as admin_handlers

    tg = FakeTelegram()
    bot = Bot("42:TEST-TOKEN", session=tg, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = DP
    channel_id = "-1001234567890"
    async with async_session() as session:
        category_id = await session.scalar(select(Category.id).order_by(Category.sort_order).limit(1))
        session.add_all(
            [
                Admin(telegram_id=OWNER.id, name="Bek", role="owner"),
                DbUser(telegram_id=CUSTOMER.id, name="Aziz"),
                Product(
                    title="Cargo shim",
                    price=289_000,
                    category_id=category_id,
                    photos=["p1", "p2"],
                    colors=["Qora"],
                    sizes=["30", "32"],
                ),
            ]
        )
        await session.commit()
        await set_setting(session, "channel_id", channel_id)
        product_id = await session.scalar(select(Product.id))

    # One tap posts the album with a branded caption plus an order button that deep-links into the bot.
    await dp.feed_update(bot, callback_update(OWNER, f"apc:{product_id}"))
    album = [c for c in tg.calls if type(c).__name__ == "SendMediaGroup"]
    assert len(album) == 1 and album[0].chat_id == channel_id and len(album[0].media) == 2
    caption = str(album[0].media[0].caption)
    assert t.BRAND in caption and "#futbolkalar" in caption and "289 000 so'm" in caption
    button_posts = [c for c in tg.calls if type(c).__name__ == "SendMessage" and c.chat_id == channel_id]
    assert button_posts and f"start=p_{product_id}" in str(button_posts[0].reply_markup)
    async with async_session() as session:
        posted = await session.get(Product, product_id)
    assert posted is not None and posted.channel_message_id is not None

    # The deep link opens that exact product card for the customer.
    await dp.feed_update(bot, text_update(CUSTOMER, f"/start p_{product_id}"))
    assert any("Cargo shim" in text for text in tg.texts_to(CUSTOMER.id))

    # Broadcast copies the admin's message to every customer and reports back.
    await dp.feed_update(bot, callback_update(OWNER, "a:bc"))
    await dp.feed_update(bot, text_update(OWNER, "🔥 Yangi drop!"))
    await dp.feed_update(bot, callback_update(OWNER, "bc:go"))
    await asyncio.gather(*admin_handlers._background)
    copies = [c for c in tg.calls if type(c).__name__ == "CopyMessage"]
    assert [c.chat_id for c in copies] == [CUSTOMER.id]
    assert any("Xabar tarqatildi" in text for text in tg.texts_to(OWNER.id))
