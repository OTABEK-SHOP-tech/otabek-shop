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
    text,
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
    balance: Mapped[int] = mapped_column(Integer, default=0)
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
    emoji: Mapped[str] = mapped_column(String(16), default="👕")
    sort_order: Mapped[int] = mapped_column(Integer, default=100)


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text, default="")
    price: Mapped[int] = mapped_column(Integer)  # sale price, so'm
    old_price: Mapped[int | None] = mapped_column(Integer, nullable=True)  # chegirma narxi
    cost_cny: Mapped[float | None] = mapped_column(Float, nullable=True)  # Pinduoduo price, yuan
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"), index=True)
    photos: Mapped[list[str]] = mapped_column(JSON, default=list)  # URLs or Telegram file_ids
    colors: Mapped[list[str]] = mapped_column(JSON, default=list)
    sizes: Mapped[list[str]] = mapped_column(JSON, default=list)
    in_stock: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    is_new: Mapped[bool] = mapped_column(Boolean, default=True)
    is_hit: Mapped[bool] = mapped_column(Boolean, default=False)
    views: Mapped[int] = mapped_column(Integer, default=0)
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
    city: Mapped[str] = mapped_column(String(64), default="")
    address: Mapped[str] = mapped_column(String(255))
    items: Mapped[list[dict[str, Any]]] = mapped_column(JSON)  # snapshot: title, price, color, size, qty, photo
    total: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(16), default="new", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    amount: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(32), default="pending")  # pending, completed, cancelled
    provider: Mapped[str] = mapped_column(String(32), default="manual")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="")


DEFAULT_SETTINGS: dict[str, str] = {
    "contact_username": "bekstyle_admin",
    "yuan_rate": "1850",
    "markup_percent": "35",
    "delivery_text": "10-18 kun ichida O'zbekiston bo'ylab yetkaziladi",
    "channel_id": "",
    "channel_username": "bekstyle_uz",
}

DEFAULT_CATEGORIES: list[tuple[str, str]] = [
    ("👕", "Futbolkalar"),
    ("🧥", "Hudi va svitshotlar"),
    ("👖", "Shimlar"),
    ("🧥", "Kurtkalar"),
    ("👟", "Oyoq kiyim"),
    ("🧢", "Aksessuarlar"),
]

DEFAULT_PRODUCTS = [
    {
        "title": "Oversize Hudi 'TOKYO STREET' (Heavyweight)",
        "description": "Premium zich paxtali mato (420g/m²). Ichki qismi yumshoq flis, erkin boxy fit bichim. Streetwear uslubi uchun eng qulay tanlov.",
        "price": 380000,
        "old_price": 450000,
        "category_name": "Hudi va svitshotlar",
        "photos": [
            "https://images.unsplash.com/photo-1556905055-8f358a7a47b2?w=800&q=80",
            "https://images.unsplash.com/photo-1509967419530-da38b4704bc6?w=800&q=80",
        ],
        "colors": ["Qora", "Grafit", "Zaytun"],
        "sizes": ["M", "L", "XL", "XXL"],
        "is_hit": True,
        "is_new": True,
    },
    {
        "title": "Tactical Multi-Pocket Kargo Shim",
        "description": "Erkin kiyinish uchun keng kargo shimlar. 6 ta mustahkam cho'ntak, pastki qismi elastik bog'ichli. Chidamli ripstop mato.",
        "price": 340000,
        "old_price": 390000,
        "category_name": "Shimlar",
        "photos": [
            "https://images.unsplash.com/photo-1624378439575-d8705ad7ae80?w=800&q=80",
            "https://images.unsplash.com/photo-1517445312882-bc9910d016b7?w=800&q=80",
        ],
        "colors": ["Qora", "Xaki", "To'q kulrang"],
        "sizes": ["30", "32", "34", "36"],
        "is_hit": True,
        "is_new": False,
    },
    {
        "title": "Graphic Boxy Fit Futbolka 'BEK 01'",
        "description": "100% tabiiy zich paxta (240g/m²). Nafas oluvchi, yuvilganda shaklini yo'qotmaydigan zamonaviy streetwear futbolka.",
        "price": 190000,
        "old_price": 240000,
        "category_name": "Futbolkalar",
        "photos": [
            "https://images.unsplash.com/photo-1521572267360-ee0c2909d518?w=800&q=80",
            "https://images.unsplash.com/photo-1583743814966-8936f5b7be1a?w=800&q=80",
        ],
        "colors": ["Qora", "Oq", "Bej"],
        "sizes": ["S", "M", "L", "XL"],
        "is_hit": False,
        "is_new": True,
    },
    {
        "title": "Y2K Baggy Vintage Jinsi Shim",
        "description": "Keng (baggy) fasonli vintage jinsi. 100% paxta denim, mustahkam choklar va zamonaviy yigitlar uslubi.",
        "price": 360000,
        "old_price": None,
        "category_name": "Shimlar",
        "photos": [
            "https://images.unsplash.com/photo-1542272604-780c96856592?w=800&q=80",
        ],
        "colors": ["Och ko'k", "Qora"],
        "sizes": ["M", "L", "XL"],
        "is_hit": True,
        "is_new": True,
    },
    {
        "title": "MA-1 Streetwear Bomber Kurtka",
        "description": "Suv o'tkazmaydigan zich neylon mato, yengidagi taktik cho'ntak va qalin astar. Bahor va kuz uchun ajoyib himoya.",
        "price": 540000,
        "old_price": 620000,
        "category_name": "Kurtkalar",
        "photos": [
            "https://images.unsplash.com/photo-1544441893-675973e31985?w=800&q=80",
        ],
        "colors": ["Qora", "Zaytun yashil"],
        "sizes": ["L", "XL", "XXL"],
        "is_hit": True,
        "is_new": False,
    },
    {
        "title": "Retro Chunky Krossovka 'URBAN GLIDE'",
        "description": "Qulay ortopedik amortizatsiyali taglik, zamonaviy ko'p qatlamli dizayn. Kundalik faol yurish uchun.",
        "price": 480000,
        "old_price": 560000,
        "category_name": "Oyoq kiyim",
        "photos": [
            "https://images.unsplash.com/photo-1552346154-21d32810aba3?w=800&q=80",
            "https://images.unsplash.com/photo-1539185441755-769473a23570?w=800&q=80",
        ],
        "colors": ["Oq / Kulrang", "Qora / Yashil"],
        "sizes": ["40", "41", "42", "43", "44"],
        "is_hit": True,
        "is_new": True,
    },
    {
        "title": "Crossbody Taktik Ko'krak Sumkasi",
        "description": "Suvga chidamli Oxford mato, ko'p qavatli ajratgichlar va baquvvat fastex qisqichlar. Telefon, hamyon va kalitlar uchun.",
        "price": 140000,
        "old_price": 180000,
        "category_name": "Aksessuarlar",
        "photos": [
            "https://images.unsplash.com/photo-1553062407-98eeb64c6a62?w=800&q=80",
        ],
        "colors": ["Qora", "Xaki"],
        "sizes": ["Standart"],
        "is_hit": False,
        "is_new": False,
    },
    {
        "title": "Acid Wash Yigitlar Svitshoti",
        "description": "Vintage yuvilgan effektli qalin paxta matosi. Ichki qismi terlatmaydi, bo'yin va manjetlari elastik.",
        "price": 310000,
        "old_price": 370000,
        "category_name": "Hudi va svitshotlar",
        "photos": [
            "https://images.unsplash.com/photo-1578587018452-892bacefd3f2?w=800&q=80",
        ],
        "colors": ["Grafit", "To'q ko'k"],
        "sizes": ["M", "L", "XL"],
        "is_hit": False,
        "is_new": True,
    },
]

connect_args: dict[str, Any] = {}
if "postgresql" in settings.DATABASE_URL:
    connect_args = {
        "statement_cache_size": 0,
        "timeout": 30,
        "command_timeout": 30,
    }

engine = create_async_engine(
    settings.DATABASE_URL,
    future=True,
    pool_pre_ping=True,
    connect_args=connect_args,
)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db():
    async with async_session() as session:
        yield session


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


async def seed_categories(session: AsyncSession) -> dict[str, int]:
    cat_map: dict[str, int] = {}
    for i, (emoji, name) in enumerate(DEFAULT_CATEGORIES):
        res = await session.execute(select(Category).where(Category.name == name))
        cat = res.scalars().first()
        if not cat:
            cat = Category(name=name, emoji=emoji, sort_order=i * 10)
            session.add(cat)
            await session.flush()
        cat_map[name] = cat.id
    await session.commit()
    return cat_map


async def seed_default_products(session: AsyncSession, cat_map: dict[str, int]) -> None:
    prod_count = (await session.execute(select(Product.id).limit(1))).first()
    if prod_count:
        return

    for item in DEFAULT_PRODUCTS:
        cat_id = cat_map.get(item["category_name"])
        if not cat_id:
            continue
        prod = Product(
            title=item["title"],
            description=item["description"],
            price=item["price"],
            old_price=item.get("old_price"),
            category_id=cat_id,
            photos=item["photos"],
            colors=item["colors"],
            sizes=item["sizes"],
            is_new=item.get("is_new", True),
            is_hit=item.get("is_hit", False),
            in_stock=True,
        )
        session.add(prod)
    await session.commit()


async def migrate_columns() -> None:
    """Safe schema column updates for existing PostgreSQL or SQLite databases."""
    columns_to_add = [
        ("users", "balance", "INTEGER DEFAULT 0"),
        ("orders", "city", "VARCHAR(64) DEFAULT ''"),
        ("products", "old_price", "INTEGER"),
        ("products", "is_new", "BOOLEAN DEFAULT TRUE"),
        ("products", "is_hit", "BOOLEAN DEFAULT FALSE"),
        ("products", "views", "INTEGER DEFAULT 0"),
    ]
    for table, col, col_def in columns_to_add:
        try:
            async with engine.begin() as conn:
                dialect = conn.dialect.name
                if dialect == "postgresql":
                    await conn.execute(text(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {col} {col_def}"))
                elif dialect == "sqlite":
                    await conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {col_def}"))
        except Exception as exc:
            logger.debug("Migration column %s.%s notice: %s", table, col, exc)


async def init_db() -> None:
    Path(settings.DATA_DIR).mkdir(parents=True, exist_ok=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await migrate_columns()
    async with async_session() as session:
        cat_map = await seed_categories(session)
        await seed_default_products(session, cat_map)
