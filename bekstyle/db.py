from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    select,
)
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from bekstyle.config import settings


def utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    telegram_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), default="")
    username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    blocked_bot: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Admin(Base):
    __tablename__ = "admins"

    telegram_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), default="")
    role: Mapped[str] = mapped_column(String(16), default="admin")  # owner | admin
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), unique=True)
    emoji: Mapped[str] = mapped_column(String(16), default="▫️")
    sort_order: Mapped[int] = mapped_column(Integer, default=100)


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text, default="")
    price: Mapped[int] = mapped_column(Integer)  # sale price, so'm
    cost_cny: Mapped[float | None] = mapped_column(Float, nullable=True)  # Pinduoduo price, yuan
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"), index=True)
    photos: Mapped[list[str]] = mapped_column(JSON, default=list)  # Telegram file_ids
    colors: Mapped[list[str]] = mapped_column(JSON, default=list)
    sizes: Mapped[list[str]] = mapped_column(JSON, default=list)
    in_stock: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    channel_message_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    category: Mapped[Category] = relationship(lazy="joined")


class CartItem(Base):
    __tablename__ = "cart_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    color: Mapped[str | None] = mapped_column(String(64), nullable=True)
    size: Mapped[str | None] = mapped_column(String(32), nullable=True)
    qty: Mapped[int] = mapped_column(Integer, default=1)

    product: Mapped[Product] = relationship(lazy="joined")


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    customer_name: Mapped[str] = mapped_column(String(255))
    customer_username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    phone: Mapped[str] = mapped_column(String(32))
    address: Mapped[str] = mapped_column(String(255))
    items: Mapped[list[dict[str, Any]]] = mapped_column(JSON)  # snapshot: title, price, color, size, qty
    total: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(16), default="new", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="")


DEFAULT_SETTINGS: dict[str, str] = {
    "contact_username": "",
    "yuan_rate": "1800",  # so'm per 1 yuan; the owner updates it from ⚙️ Sozlamalar
    "markup_percent": "40",
    "delivery_text": "15–25 kun",
    "channel_id": "",
    "channel_username": "",
}

DEFAULT_CATEGORIES: list[tuple[str, str]] = [
    ("👕", "Futbolkalar"),
    ("🧥", "Hudi va svitshotlar"),
    ("👖", "Shimlar"),
    ("🧥", "Kurtkalar"),
    ("👟", "Oyoq kiyim"),
    ("🧢", "Aksessuarlar"),
]

# shortcut: SQLite only (aiosqlite); add asyncpg and a postgresql+asyncpg URL to move to Postgres.
engine = create_async_engine(settings.DATABASE_URL, future=True)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_setting(session: AsyncSession, key: str) -> str:
    row = await session.get(Setting, key)
    return row.value if row else DEFAULT_SETTINGS.get(key, "")


async def set_setting(session: AsyncSession, key: str, value: str) -> None:
    row = await session.get(Setting, key)
    if row:
        row.value = value
    else:
        session.add(Setting(key=key, value=value))
    await session.commit()


async def seed_categories(session: AsyncSession) -> None:
    if (await session.execute(select(Category.id).limit(1))).first():
        return
    session.add_all(
        Category(name=name, emoji=emoji, sort_order=i * 10) for i, (emoji, name) in enumerate(DEFAULT_CATEGORIES)
    )
    await session.commit()


async def init_db() -> None:
    Path(settings.DATA_DIR).mkdir(parents=True, exist_ok=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with async_session() as session:
        await seed_categories(session)
