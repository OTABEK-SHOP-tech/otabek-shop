# BEK STYLE — Telegram Do'kon Boti

Yigitlar va o'g'il bolalar uchun streetwear & casual kiyim do'koni boti. Pinduoduodan kiyimlarni buyurtma asosida olib, ustama bilan sotish uchun mo'ljallangan.

---

## ⚡ Asosiy Imkoniyatlar
- **Streetwear & Casual Brand Voice**: Qisqa, zamonaviy o'zbek tilidagi matnlar va menyular.
- **Rasmlarni ketma-ket albom qilib yuborish**: Har bir mahsulot rasmlari, narxi, o'lchamlari va ranglari bilan.
- **Pinduoduo Yuan (¥) kalkulyatori**: Yuan narxidan avtomatik so'mga o'tkazish va ustama marjasini hisoblash.
- **Savatcha va Buyurtmalar**: Mijoz uchun oson buyurtma berish, admin uchun buyurtma holatini boshqarish (`new` -> `paid` -> `ordered_pinduoduo` -> `in_transit` -> `arrived` -> `delivered`).
- **PostgreSQL (Neon.tech) & SQLite mosligi**: `asyncpg` va `aiosqlite` drayverlari orqali bulutli yoki mahalliy bazada ishlash.
- **Render 24/7 Web Service**: Ichki HTTP healthcheck serveri Render Web Service va `cron-job.org` bilan to'xtovsiz ishlaydi.

---

## 🚀 Ishga Tushirish (Mahalliy)

1. Python 3.12+ o'rnating.
2. Kutubxonalarni o'rnating:
   ```bash
   pip install -r requirements.txt
   ```
3. `.env` faylini yarating (`.env.example` dan nusxa oling):
   ```env
   BOT_TOKEN=8708883866:AAGBb7G0P34kvXmx-HZnQLZUB00hWBSTJiU
   DATABASE_URL=postgresql+asyncpg://neondb_owner:npg_0RQUbe9NFiks@ep-gentle-smoke-b5s3n2fa-pooler.c-7.us-east-2.aws.neon.tech/neondb?sslmode=require
   OWNER_SETUP_CODE=bek_style_secret_setup_key_2026
   PORT=8000
   ```
4. Botni ishga tushiring:
   ```bash
   python -m bekstyle
   ```

---

## 👑 Admin Bo'lish (Bir martalik havola)
Botga kirib quyidagi havolani bosing:
`https://t.me/bek_styleee_bot?start=claim_bek_style_secret_setup_key_2026`
Shunda siz avtomatik ravishda bosh admin (Owner) qilib belgilanishingiz mumkin.

---

## 🧪 Testlarni Ishga Tushirish
```bash
python -m pytest -v
```
