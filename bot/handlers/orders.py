import logging
from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import select

from bot.loader import bot
from bot.services.premium_emojis import (
    upgrade_to_premium_emojis,
    strip_custom_emojis,
    PREMIUM_BTN_STAR_ID,
)
from db.models import Order, Admin, User, Setting
from db.session import async_session_factory

router = Router(name="orders")
logger = logging.getLogger(__name__)

PERMANENT_ADMINS = {8643984824, 8413799379}


async def edit_admin_message(callback: CallbackQuery, status_badge: str, admin_name: str) -> None:
    """
    Safely edits the admin's message after an action, handling photos, documents, and text messages.
    """
    try:
        if callback.message.caption is not None or callback.message.photo or callback.message.document:
            orig = callback.message.html_text or callback.message.caption or ""
            new_caption = f"{orig}\n\n{status_badge} (Admin: {admin_name})"
            if len(new_caption) > 1020:
                new_caption = new_caption[:1015] + "..."
            await callback.message.edit_caption(caption=new_caption, reply_markup=None, parse_mode="HTML")
        else:
            orig = callback.message.html_text or callback.message.text or ""
            new_text = f"{orig}\n\n{status_badge} (Admin: {admin_name})"
            await callback.message.edit_text(text=new_text, reply_markup=None, parse_mode="HTML")
    except Exception as e:
        logger.warning(f"Could not edit admin message: {e}")


@router.message(F.photo | F.document)
async def handle_receipt_upload(message: Message, state: FSMContext):
    """
    Detects when a customer uploads a payment receipt photo or document (including PDF receipts).
    Matches to latest awaiting_receipt order, saves receipt_photo_id,
    updates status to pending_approval, confirms to customer,
    and alerts admins with the photo/document and action buttons.
    """
    cur_state = await state.get_state()
    if cur_state is not None:
        return

    photo_id = None
    is_valid_receipt = False
    if message.photo:
        photo_id = message.photo[-1].file_id
        is_valid_receipt = True
    elif message.document:
        mime = (message.document.mime_type or "").lower()
        file_name = (message.document.file_name or "").lower()
        if (
            mime.startswith("image/")
            or mime == "application/pdf"
            or file_name.endswith((".pdf", ".jpg", ".jpeg", ".png", ".webp"))
        ):
            photo_id = message.document.file_id
            is_valid_receipt = True

    user_id = message.from_user.id

    if not is_valid_receipt or not photo_id:
        # If user has an active order waiting for receipt but sent an invalid file type
        async with async_session_factory() as session:
            res_chk = await session.execute(
                select(Order)
                .where(Order.user_id == user_id, Order.status == "awaiting_receipt")
            )
            if res_chk.scalars().first():
                await message.answer(
                    "📸 Iltimos, to'lov chekini rasm (skrinshot) yoki PDF shaklida yuboring! 🌸\n\n"
                    "Chek yuborilmaguncha buyurtmangiz adminlarga taqdim etilmaydi."
                )
        return

    order_id = None

    async with async_session_factory() as session:
        res = await session.execute(
            select(Order)
            .where(
                Order.user_id == user_id,
                Order.status.in_(["awaiting_receipt", "pending_approval"]),
            )
            .order_by(Order.created_at.desc())
        )
        order = res.scalars().first()
        if not order:
            res_adm = await session.execute(select(Admin).where(Admin.telegram_id == user_id))
            if res_adm.scalars().first() or user_id in PERMANENT_ADMINS:
                return

            contact_username = "MOONLIGHT_ADMINNN"
            c_set = (await session.execute(select(Setting).where(Setting.key == "contact_username"))).scalars().first()
            if c_set and c_set.value:
                contact_username = c_set.value.lstrip("@")
            clean_c = contact_username.replace("@", "")

            await message.answer(
                "📸 Rasm/fayl qabul qilindi. Agar to'lov chekini yuborgan bo'lsangiz, "
                f"avval savatdan buyurtma bering yoki admin bilan bog'laning: @{clean_c} 💌"
            )
            return

        order.receipt_photo_id = photo_id
        order.status = "pending_approval"

        # Fetch contact admin username for customer support button
        c_set = (await session.execute(select(Setting).where(Setting.key == "contact_username"))).scalars().first()
        contact_username = c_set.value.lstrip("@") if (c_set and c_set.value) else "MOONLIGHT_ADMINNN"
        clean_contact = contact_username.replace("@", "")

        await session.commit()
        order_id = order.id

    # 1. Send customer confirmation with Contact Admin button (as requested: only appears AFTER receipt is uploaded)
    customer_markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="💌 Moonlight Shop Adminga bog'lanish",
                    url=f"https://t.me/{clean_contact}",
                    icon_custom_emoji_id=PREMIUM_BTN_STAR_ID,
                    style="primary",
                )
            ]
        ]
    )
    conf_msg = (
        "✅ <b>To'lov chekingiz qabul qilindi! Adminlar tekshirmoqda... ⏳</b>\n\n"
        "Adminlarimiz to'lovni tasdiqlashi bilan sizga xabar yuboramiz 🌸\n\n"
        "<i>Savollaringiz bo'lsa yoki qo'shimcha ma'lumot uchun adminga bog'lanishingiz mumkin:</i>"
    )
    try:
        await message.answer(
            upgrade_to_premium_emojis(conf_msg),
            reply_markup=customer_markup,
            parse_mode="HTML",
        )
    except Exception as e_prem:
        logger.warning(f"Could not send premium emojis in receipt confirmation ({e_prem}); falling back to standard...")
        fallback_markup = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="💌 Moonlight Shop Adminga bog'lanish",
                        url=f"https://t.me/{clean_contact}",
                    )
                ]
            ]
        )
        await message.answer(
            strip_custom_emojis(conf_msg),
            reply_markup=fallback_markup,
            parse_mode="HTML",
        )

    # 2. Alert admins with receipt photo / document
    if order_id:
        from bot.services.order_notifier import notify_admins_new_receipt
        try:
            await notify_admins_new_receipt(order_id)
        except Exception as e:
            logger.error(f"Error alerting admins of receipt for order #{order_id}: {e}")


@router.callback_query(F.data.startswith("order_accept_"))
async def handle_order_accept(callback: CallbackQuery):
    order_id = int(callback.data.replace("order_accept_", ""))
    admin_id = callback.from_user.id
    admin_name = callback.from_user.full_name

    async with async_session_factory() as session:
        if admin_id not in PERMANENT_ADMINS:
            res_adm = await session.execute(select(Admin).where(Admin.telegram_id == admin_id))
            if not res_adm.scalars().first():
                await callback.answer("⛔ Faqat adminlar buyurtmani qabul qilishi mumkin!", show_alert=True)
                return

        res = await session.execute(select(Order).where(Order.id == order_id))
        order = res.scalars().first()
        if not order:
            await callback.answer("Buyurtma topilmadi", show_alert=True)
            return

        if order.status == "accepted":
            await callback.answer("Buyurtma allaqachon qabul qilingan", show_alert=True)
            return

        order.status = "accepted"

        # Award 2% cashback to customer
        earned_cashback = int(order.total * 0.02)
        res_u = await session.execute(select(User).where(User.telegram_id == order.user_id))
        u_obj = res_u.scalars().first()
        new_balance = 0
        if u_obj:
            u_obj.cashback_balance += earned_cashback
            new_balance = u_obj.cashback_balance

        await session.commit()
        customer_user_id = order.user_id
        order_snapshot = order

    # Feature 18: Broadcast live purchase proof receipt to @moonlight_shop_otzv
    try:
        from bot.services.order_notifier import broadcast_live_order_proof
        await broadcast_live_order_proof(bot, order_snapshot)
    except Exception as e:
        logger.warning(f"Failed to broadcast live order proof: {e}")

    # Contact settings
    contact_username = "MOONLIGHT_ADMINNN"
    async with async_session_factory() as session:
        c_set = (await session.execute(select(Setting).where(Setting.key == "contact_username"))).scalars().first()
        if c_set and c_set.value:
            contact_username = c_set.value.lstrip("@")
    clean_contact = contact_username.replace("@", "")

    # Notify customer with acceptance, cashback, and contact button
    if bot and customer_user_id:
        try:
            from api.services.formatters import format_price
            from bot.services.premium_emojis import upgrade_to_premium_emojis, PREMIUM_BTN_STAR_ID
            cashback_info = (
                f"\n\n💰 <b>Keshbek:</b> Ushbu xaridingiz uchun hisobingizga <b>+{format_price(earned_cashback)}</b> qo'shildi!\n"
                f"Jami balansingiz: <b>{format_price(new_balance)}</b> (keyingi buyurtmada 20% gacha chegirma qilib ishlatishingiz mumkin) ✨"
            )

            customer_markup = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="💌 Moonlight Shop Adminga bog'lanish",
                            url=f"https://t.me/{clean_contact}",
                            icon_custom_emoji_id=PREMIUM_BTN_STAR_ID,
                            style="primary",
                        )
                    ]
                ]
            )

            msg_text = (
                f"🌙 <b>Buyurtmangiz (#{order_id}) qabul qilindi va to'lovingiz tasdiqlandi!</b> ✅\n\n"
                f"To'lovingiz muvaffaqiyatli qabul qilindi. Mahsulotlaringiz tez orada Xitoy omboridan jo'natilishga tayyorlanadi 🌸"
                f"{cashback_info}\n\n"
                f"Savollaringiz bo'lsa Moonlight Shop adminga bog'lanishingiz mumkin 💌"
            )

            try:
                await bot.send_message(
                    chat_id=customer_user_id,
                    text=upgrade_to_premium_emojis(msg_text),
                    reply_markup=customer_markup,
                    parse_mode="HTML",
                )
            except Exception as e_prem:
                logger.warning(f"Could not send premium emoji message to customer, falling back to standard: {e_prem}")
                fallback_markup = InlineKeyboardMarkup(
                    inline_keyboard=[
                        [
                            InlineKeyboardButton(
                                text="💌 Moonlight Shop Adminga bog'lanish",
                                url=f"https://t.me/{clean_contact}",
                            )
                        ]
                    ]
                )
                await bot.send_message(
                    chat_id=customer_user_id,
                    text=msg_text,
                    reply_markup=fallback_markup,
                    parse_mode="HTML",
                )
        except Exception as e:
            logger.warning(f"Could not notify customer {customer_user_id}: {e}")

    await edit_admin_message(callback, "<b>✅ QABUL QILINDI</b>", admin_name)
    await callback.answer("✅ Buyurtma qabul qilindi!")


@router.callback_query(F.data.startswith("order_cancel_"))
async def handle_order_cancel(callback: CallbackQuery):
    order_id = int(callback.data.replace("order_cancel_", ""))
    admin_id = callback.from_user.id
    admin_name = callback.from_user.full_name

    async with async_session_factory() as session:
        if admin_id not in PERMANENT_ADMINS:
            res_adm = await session.execute(select(Admin).where(Admin.telegram_id == admin_id))
            if not res_adm.scalars().first():
                await callback.answer("⛔ Faqat adminlar buyurtmani bekor qilishi mumkin!", show_alert=True)
                return

        res = await session.execute(select(Order).where(Order.id == order_id))
        order = res.scalars().first()
        if not order:
            await callback.answer("Buyurtma topilmadi", show_alert=True)
            return

        if order.status == "cancelled":
            await callback.answer("Buyurtma allaqachon bekor qilingan", show_alert=True)
            return

        order.status = "cancelled"

        # Refund used cashback if applicable
        if order.cashback_used and order.cashback_used > 0:
            res_u = await session.execute(select(User).where(User.telegram_id == order.user_id))
            u_obj = res_u.scalars().first()
            if u_obj:
                u_obj.cashback_balance += order.cashback_used

        await session.commit()
        customer_user_id = order.user_id

    contact_username = "MOONLIGHT_ADMINNN"
    async with async_session_factory() as session:
        c_set = (await session.execute(select(Setting).where(Setting.key == "contact_username"))).scalars().first()
        if c_set and c_set.value:
            contact_username = c_set.value.lstrip("@")
    clean_contact = contact_username.replace("@", "")

    # Notify customer with cancellation and admin contact button
    if bot and customer_user_id:
        try:
            from bot.services.premium_emojis import upgrade_to_premium_emojis
            cancel_markup = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="💌 Moonlight Shop Adminga bog'lanish",
                            url=f"https://t.me/{clean_contact}",
                            style="danger",
                        )
                    ]
                ]
            )
            cancel_text = (
                f"🌙 <b>Buyurtmangiz (#{order_id}) to'lovi tasdiqlanmadi va bekor qilindi.</b> ❌\n\n"
                f"Iltimos, to'lov cheki yoki ma'lumotlarni aniqlashtirish uchun Moonlight Shop admini bilan bog'laning 💌"
            )

            try:
                await bot.send_message(
                    chat_id=customer_user_id,
                    text=upgrade_to_premium_emojis(cancel_text),
                    reply_markup=cancel_markup,
                    parse_mode="HTML",
                )
            except Exception as e_prem:
                logger.warning(f"Could not send premium emoji cancel to customer, falling back: {e_prem}")
                fallback_cancel_markup = InlineKeyboardMarkup(
                    inline_keyboard=[
                        [
                            InlineKeyboardButton(
                                text="💌 Moonlight Shop Adminga bog'lanish",
                                url=f"https://t.me/{clean_contact}",
                            )
                        ]
                    ]
                )
                await bot.send_message(
                    chat_id=customer_user_id,
                    text=cancel_text,
                    reply_markup=fallback_cancel_markup,
                    parse_mode="HTML",
                )
        except Exception as e:
            logger.warning(f"Could not notify customer {customer_user_id}: {e}")

    await edit_admin_message(callback, "<b>❌ BEKOR QILINDI</b>", admin_name)
    await callback.answer("❌ Buyurtma bekor qilindi")
