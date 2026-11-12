import asyncio
from datetime import datetime, timezone
from sqlalchemy import select
from db.session import async_session_factory, init_db
from db.models import Category, Product, Setting, Review, User, Admin


async def seed_database() -> None:
    await init_db()
    async with async_session_factory() as session:
        # 0. Ensure permanent store owners
        existing_admins = (await session.execute(select(Admin))).scalars().all()
        admin_ids = {a.telegram_id for a in existing_admins}
        added_admin = False
        if 8643984824 not in admin_ids:
            session.add(Admin(telegram_id=8643984824, name="Otabek.", username="obidjonovic2", role="owner"))
            added_admin = True
        if 8413799379 not in admin_ids:
            session.add(Admin(telegram_id=8413799379, name="💞Gulmira💞", username="MOONLIGHT_ADMINNN", role="owner"))
            added_admin = True
        else:
            # Update username if already in admins
            for a in existing_admins:
                if a.telegram_id == 8413799379:
                    a.username = "MOONLIGHT_ADMINNN"
                    added_admin = True
        if added_admin:
            await session.commit()

        # 1. Categories
        res_cat = await session.execute(select(Category))
        if res_cat.scalars().first() is None:
            categories = [
                Category(slug="jempir", name="Jempir & Sviter", emoji="🧶", sort_order=1),
                Category(slug="wig", name="Pariklar (Wigs)", emoji="💇‍♀️", sort_order=2),
                Category(slug="scarf", name="Sharf & Ro'mol", emoji="🧣", sort_order=3),
                Category(slug="sumka", name="Sumkalar", emoji="👜", sort_order=4),
                Category(slug="aksessuar", name="Aksessuarlar", emoji="🎀", sort_order=5),
            ]
            session.add_all(categories)
            await session.commit()

        # 2. Settings
        res_set = await session.execute(select(Setting))
        if res_set.scalars().first() is None:
            default_settings = [
                Setting(key="cargo_rate", value="10000"),  # 10.000 so'm / 100g (AVTO)
                Setting(key="cargo_rate_avto", value="10000"),  # 10.000 so'm / 100g
                Setting(key="cargo_rate_avia", value="14000"),  # 14.000 so'm / 100g
                Setting(key="cargo_profit_per_100g", value="2000"),  # 2.000 so'm foyda
                Setting(key="delivery_days_avto", value="14–18 kun"),
                Setting(key="delivery_days_avia", value="7–9 kun"),
                Setting(key="delivery_days", value="7–18 kun"),
                Setting(key="delivery_scope", value="O'zbekiston bo'ylab"),
                Setting(key="payment_terms", value="100% oldindan to'lov"),
                Setting(key="payment_card", value="9860 3501 4255 8658 (Humo, Ma'rufjonova Gulmira)"),
                Setting(key="location", value="Toshkent"),
                Setting(key="contact_username", value="MOONLIGHT_ADMINNN"),
                Setting(key="channel_url", value="https://t.me/moonlight_chinese_shop"),
                Setting(key="channel_id", value="-1004378811161"),
                Setting(key="chat_url", value="https://t.me/MY_interesno"),
                Setting(key="chat_id", value="-1003565030513"),
                Setting(key="owner_claimed_at", value=""),
                Setting(key="welcome_text", value="Moonlight Chinese Shop ga xush kelibsiz! 🌙 Xitoy brendlari va aesthetic kiyimlar do'koni."),
            ]
            session.add_all(default_settings)
            await session.commit()

        # 3. Products
        res_prod = await session.execute(select(Product))
        if res_prod.scalars().first() is None:
            demo_products = [
                Product(
                    title="Aesthetic Vintage Pushti Jempir 🌸",
                    description="Yumshoq, qulay va iliq pushti jempir. Aesthetic koreys va xitoy uslubidagi qizlar uchun ajoyib tanlov! Qalin to'qilgan, qishki va kuzgi ob-havo uchun mos. 🎀",
                    price=99000,
                    old_price=135000,
                    category="jempir",
                    photos=["demo_jempir_1.png", "demo_jempir_2.png"],
                    sizes=["S", "M", "L"],
                    colors=["Aesthetic pushti 🌸", "Sutli oq 🤍", "Krem 🍦"],
                    weight_grams=350,
                    in_stock=True,
                    is_new=True,
                    is_hit=True,
                    views=128,
                ),
                Product(
                    title="Pastel Pushti Lolita Parik (Wig) 💇‍♀️",
                    description="Yuqori sifatli termotola, tabiiy jilo va yumshoq jingalaklar. Cosplay va kundalik aesthetic obrazlar uchun mukammal! Oson taraladi va shaklini saqlaydi. ✨",
                    price=125000,
                    old_price=160000,
                    category="wig",
                    photos=["demo_wig_1.png", "demo_wig_2.png"],
                    sizes=["Universal"],
                    colors=["Pastel pushti 🌸", "Och binafsha 💜"],
                    weight_grams=250,
                    in_stock=True,
                    is_new=True,
                    is_hit=False,
                    views=89,
                ),
                Product(
                    title="Iliq Yulduzli Shoyi Sharf 🧣",
                    description="Yumshoq jun va ipak aralashmasidan tayyorlangan zamonaviy sharf. Sovuq kunlarda issiq saqlaydi va har qanday kiyimga noziklik bag'ishlaydi. 💗",
                    price=45000,
                    old_price=60000,
                    category="scarf",
                    photos=["demo_scarf_1.png", "demo_scarf_2.png"],
                    sizes=["200x50 sm"],
                    colors=["Pushti-krem 🌸", "Kulrang-pushti 🎀"],
                    weight_grams=180,
                    in_stock=True,
                    is_new=False,
                    is_hit=True,
                    views=215,
                ),
            ]
            session.add_all(demo_products)
            await session.commit()

        # 4. Reviews
        res_rev = await session.execute(select(Review))
        if res_rev.scalars().first() is None:
            reviews = [
                Review(
                    customer_name="Madina",
                    text="Jempir keldi, sifati juda zo'r ekan! Yumshoq va xuddi rasmdagidek chiqdi, kargo ham tez yetib keldi. Rahmat kattakon! 🌸🎀",
                    photos=["demo_review_1.png"],
                    approved=True,
                ),
                Review(
                    customer_name="Nilufar 🎀",
                    text="Parik va sharf oldim, rangi juda nozik va yoqimli. Yetkazib berish aytilgan muddatda keldi. Do'konga baraka bersin! ✨💗",
                    photos=[],
                    approved=True,
                ),
            ]
            session.add_all(reviews)
            await session.commit()


if __name__ == "__main__":
    asyncio.run(seed_database())
