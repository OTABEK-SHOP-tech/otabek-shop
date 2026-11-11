# 🌙 Moonlight Chinese Shop — Telegram Mini App & Bot

> **Bot nomi:** Moonlight chinese bot ([@moonlight_chinese_bot](https://t.me/moonlight_chinese_bot))  
> **Kanal:** Moonlight Chinese Shop  
> **Tavsif:** Xitoy brendlari, aesthetic kiyimlar, jempirlar, pariklar va aksessuarlar uchun zamonaviy Telegram Mini App do'koni.

---

## 🌟 Imkoniyatlar

1. **🛍️ Mini App Do'koni:**
   - Tezkor 2 ustunli katalog va toifalar (#hashtag).
   - "Kun mahsuloti", "Yangi kelganlar" va "Hit" karusellari.
   - Savatcha, o'lcham va rang tanlash, kargoni avtomatik hisoblash (`ceil(og'irlik / 100) * 12.000 so'm`).
   - Wishlist (sevimlilar) va mijozlar fikrlari.
2. **👑 Do'kon Egasi va Admin Boshqaruvi:**
   - **Xavfsiz biriktirish:** `https://t.me/moonlight_chinese_bot?start=claim_<OWNER_SETUP_CODE>` havolasi orqali 1-bosishda botni egasi sifatida o'zlashtirish.
   - **Sehrli import:** Kanaldagi postni botga forward qilib, 5 soniyada mahsulotga aylantirish.
   - **Kanalga 1-bosishda joylash:** Do'kondan to'g'ridan-to'g'ri kanalga chiroyli e'lon va `🛍️ Do'konda ko'rish` tugmasi bilan post qilish.
3. **🎁 7-O'rinli Referal Konkurs Tizimi:**
   - Soxta ballardan 100% himoyalangan avtomatlashtirilgan referal konkurs tizimi.
   - Kanaldan chiqib ketganlarni avtomatik hisobdan chiqarish (`ChatMemberUpdated`).
4. **📦 Kargo Trek-kodi & Promokodlar:**
   - Buyurtmalar holatini kuzatish va chegirma promokodlari arxitekturasi.

---

## 🚀 Ishga Tushirish (Local Run)

### 1. Muhitni faollashtirish
```powershell
cd "D:\Gulmira opa shop"
.\.venv\Scripts\activate
```

### 2. Frontendni build qilish (agar o'zgartirish kiritilsa)
```powershell
cmd.exe /c "npm run build --prefix webapp"
```

### 3. Server va Botni ishga tushirish
```powershell
python run.py
```

Server `http://localhost:8001` portida ishga tushadi va `@moonlight_chinese_bot` polling orqali Telegram xabarlarini qabul qiladi.

---

## 👑 Botni O'zlashtirish (Claim Owner)

1. Botni ishga tushirgach, Telegramda quyidagi havola orqali kiring:
   `https://t.me/moonlight_chinese_bot?start=claim_moonlight_owner_secret_998877_setup`
2. Bot sizni do'kon egasi deb saqlaydi va admin panelini ochadi.
3. Botni `Moonlight Chinese Shop` kanalingizga **Admin** qilib qo'shing va post chiqarish huquqini bering.
