"""Admin: order lists and status changes (each change notifies the customer)."""

from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery
from sqlalchemy import select

from bekstyle import texts as t
from bekstyle.db import Order, async_session
from bekstyle.handlers import IsAdmin, cb_int, show_in
from bekstyle.keyboards import inline
from bekstyle.notify import notify_customer_status, order_admin_view
from bekstyle.services import change_order_status

router = Router(name="admin_orders")
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())

ORDERS_LIMIT = 20


@router.callback_query(F.data.startswith("aol:"))
async def on_order_list(callback: CallbackQuery) -> None:
    archive = (callback.data or "").endswith(":archive")
    final = list(t.FINAL_STATUSES)
    status_filter = Order.status.in_(final) if archive else Order.status.notin_(final)
    async with async_session() as session:
        orders = (
            await session.scalars(select(Order).where(status_filter).order_by(Order.id.desc()).limit(ORDERS_LIMIT))
        ).all()
    rows = [
        [
            (
                f"#{o.id} · {t.status_label(o.status)} · {t.clip(o.customer_name, 14)} · {t.format_price(o.total)}",
                f"ao:{o.id}",
            )
        ]
        for o in orders
    ]
    switch = ("🔥 Faol", "aol:active") if archive else ("🗂 Arxiv", "aol:archive")
    rows.append([switch, ("⬅️ Menyu", "a:menu")])
    title = f"🗂 <b>Arxiv</b> (oxirgi {ORDERS_LIMIT})" if archive else "🧾 <b>Faol buyurtmalar</b>"
    await show_in(callback, title + ("" if orders else "\nHozircha yo'q."), inline(*rows))


async def _show_order(callback: CallbackQuery, order_id: int, alert: str | None = None) -> None:
    async with async_session() as session:
        order = await session.get(Order, order_id)
    if order is None:
        await callback.answer("Buyurtma topilmadi", show_alert=True)
        return
    await show_in(callback, *order_admin_view(order), alert=alert)


@router.callback_query(F.data.startswith("ao:"))
async def on_order_view(callback: CallbackQuery) -> None:
    await _show_order(callback, cb_int(callback, 1))


@router.callback_query(F.data.startswith("oc:"))
async def on_order_cancel_ask(callback: CallbackQuery) -> None:
    order_id = cb_int(callback, 1)
    await show_in(
        callback,
        f"❌ Buyurtma #{order_id} bekor qilinsinmi? Mijozga xabar boradi.",
        inline(
            [
                ("✅ Ha, bekor qilish", f"os:{order_id}:cancelled"),
                ("⬅️ Yo'q", f"ao:{order_id}"),
            ]
        ),
    )


@router.callback_query(F.data.startswith("os:"))
async def on_order_status(callback: CallbackQuery, bot: Bot) -> None:
    _, order_id_raw, target = (callback.data or "").split(":")
    order_id = int(order_id_raw)
    async with async_session() as session:
        order = await change_order_status(session, order_id, target) if target in t.ORDER_STATUSES else None
    if order is None:
        await _show_order(callback, order_id, alert="Holat allaqachon o'zgargan")
        return
    await show_in(callback, *order_admin_view(order))
    await notify_customer_status(bot, order)
