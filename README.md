# BEK STYLE

Telegram Mini App for a made-to-order men's clothing and accessories shop.
React + Vite frontend, FastAPI + aiogram backend, and PostgreSQL/SQLite storage.

## Customer flow

Catalog → choose size/color → cart → delivery details → order total → recipient card → upload receipt.
There is no wallet or balance top-up. A receipt enters payment review; only an admin can confirm the actual bank transfer.
Cargo is billed separately after weighing and is never represented as a zero delivery charge.

The inherited eight AI sample products are explicitly identified as demo items. They remain visible for design preview, but checkout rejects them. Add actual sourced products through the existing admin tools before accepting customer orders.

## Verified Pinduoduo imports

The importer processes supplied, verified product records. It does not scrape Pinduoduo, bypass login, or discover the whole marketplace. A real source URL, official product photos, a source product ID, a recent timezone-aware `checked_at` and `verified: true` are required for each product. Each SKU must provide its actual ID, cost in CNY, stock flag, and explicit color/size (null when that option genuinely does not apply).

Every product must include explicit `costs`: `yuan_rate`, `china_shipping_cny`, `intermediary_fee_som`, and `other_costs_som`. No exchange rate or fee is assumed. `target_profit_som` must be 5000, 10000, or 30000. The retail price covers the most expensive verified SKU, all supplied costs and the target profit, rounded up to the next 1000 UZS. Cargo remains separate; net profit depends on the supplied costs being complete.

```powershell
python -m bekstyle.import_catalog verified-catalog.json
python -m bekstyle.import_catalog verified-catalog.json --apply
```

The first command previews calculated prices without loading database settings or writing. The second atomically upserts the supplied products by source ID in the configured database, preserving unrelated products. Source URLs, CNY costs, fees and profit targets stay private. Customer interfaces and checkout accept only available source color/size combinations. No import posts to Telegram channels or sends notifications.

## Environment

Create a local `.env` from `.env.example`. Never commit actual credentials.

```env
BOT_TOKEN=YOUR_BOTFATHER_TOKEN
DATABASE_URL=postgresql+asyncpg://USER:PASSWORD@HOST/DATABASE?ssl=require
OWNER_SETUP_CODE=YOUR_LONG_RANDOM_SETUP_CODE
PORT=8000
DEV_BROWSER_MODE=false
```

Public browser visits are read-only. Private actions require verified Telegram Mini App initData. Local dev bypass is disabled by default and is not accepted on Render.

## Local development

```powershell
python -m pip install -r requirements-dev.txt
cd webapp
npm ci
npm run build
cd ..
python -m bekstyle
```

The API serves `webapp/dist` locally and `bekstyle/static` in the Docker image. Use a separate local SQLite database and an empty BOT_TOKEN for offline preview so tests never poll the live bot or notify real admins.

## Render deployment

The Dockerfile builds the React frontend in a Node stage and copies the result into the Python runtime. GitHub auto-deploy can deploy commits on the configured branch; build and deployment status must be verified on Render.

Keep BOT_TOKEN, DATABASE_URL and OWNER_SETUP_CODE in Render environment variables. Use persistent PostgreSQL storage for live records. Database changes are additive. Uploaded receipt bytes are stored in the database so they survive an ephemeral container replacement. Receipt download requires the order owner's or admin's verified Telegram identity.

Health endpoint: `/health`.
Live shop: https://bek-style-shop.onrender.com
Telegram bot: https://t.me/bek_styleee_bot

## Payment behavior

- Prices, product availability and selected variants are validated on the server.
- Checkout uses an Idempotency-Key to prevent duplicate orders on retries.
- A receipt is accepted only for a pending or rejected payment, and must be a valid image/PDF of at most 10 MB.
- Admin confirmation/rejection requires the payment_review state.
- Public API responses contain sale prices, never internal cost or markup fields.
- Recipient cards are editable admin settings; they are not payer card credentials.

## Validation

```powershell
pytest -q
cd webapp
npm run build
```

Tests use temporary SQLite databases and do not contact Telegram. Live bank transfers and real customer purchases are not part of automated tests.

## Credential hygiene

If a real token/password has ever appeared in a public commit, removing its current text is insufficient: revoke/rotate it at its provider and update the deployment environment. Do not rewrite shared Git history or destroy existing data as part of routine deployment.
