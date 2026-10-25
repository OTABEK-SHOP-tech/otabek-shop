"""Entry points every user hits: /start (incl. deep links), cancel, contact, channel, fallback."""

from aiogram import F, Router
from aiogram.filters import Command, CommandObject, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message
from aiogram.types import User as TgUser

from bekstyle import texts as t
from bekstyle.db import User, async_session, get_setting
from bekstyle.handlers import menu_for
from bekstyle.handlers.catalog import send_product
from bekstyle.keyboards import main_menu
from bekstyle.notify import banner_photo, remember_banner
from bekstyle.services import claim_ownership

router = Router(name="common")
fallback_router = Router(name="fallback")  # included last, after every other router

OWNER_WELCOME = (
    f"👑 <b>Tabriklaymiz! Endi {t.BRAND} sizniki.</b>\n\n"
    "1️⃣ Botni kanalingizga admin qiling — bot o'zi ulashni taklif qiladi.\n"
    "2️⃣ ⚙️ Sozlamalar: kontakt, yuan kursi, ustama %.\n"
    "3️⃣ ➕ Mahsulot qo'shing — rasmlarni ketma-ket yuboring.\n\n"
    f"👇 «{t.BTN_ADMIN}» tugmasi pastda."
)


async def upsert_user(tg_user: TgUser) -> None:
    async with async_session() as session:
        user = await session.get(User, tg_user.id)
        if user:
            user.name, user.username, user.blocked_bot = (
                tg_user.full_name,
                tg_user.username,
                False,
            )
        else:
            session.add(
                User(
                    telegram_id=tg_user.id,
                    name=tg_user.full_name,
                    username=tg_user.username,
                )
            )
        await session.commit()


async def _handle_claim(message: Message, tg_user: TgUser, code: str) -> None:
    async with async_session() as session:
        result = await claim_ownership(session, code, tg_user.id, tg_user.full_name)
    if result == "claimed":
        await message.answer(OWNER_WELCOME, reply_markup=main_menu(True))
    elif result == "already_owner":
        await message.answer("👑 Siz allaqachon do'kon egasisiz.", reply_markup=main_menu(True))
    else:
        await message.answer(
            "❌ Havola yaroqsiz yoki allaqachon ishlatilgan.",
            reply_markup=await menu_for(tg_user.id),
        )


@router.message(CommandStart())
async def on_start(message: Message, command: CommandObject, state: FSMContext) -> None:
    tg_user = message.from_user
    if tg_user is None:
        return
    await state.clear()
    await upsert_user(tg_user)
    payload = command.args or ""
    if payload.startswith("claim_"):
        await _handle_claim(message, tg_user, payload[len("claim_") :])
        return
    menu = await menu_for(tg_user.id)
    if payload.startswith("p_") and payload[2:].isdecimal():
        await message.answer(f"🖤 <b>{t.BRAND}</b> · siz tanlagan model 👇", reply_markup=menu)
        if await send_product(message, tg_user.id, int(payload[2:])):
            return
        await message.answer("Bu model endi mavjud emas. Katalogdan boshqasini tanlang 👇")
    photo = banner_photo()
    sent = await message.answer_photo(photo, caption=t.greeting(tg_user.first_name), reply_markup=menu)
    remember_banner(photo, sent)


@router.message(StateFilter("*"), Command("cancel"))
@router.message(StateFilter("*"), F.text == t.BTN_CANCEL)
async def on_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    user_id = message.from_user.id if message.from_user else 0
    await message.answer("❌ Bekor qilindi.", reply_markup=await menu_for(user_id))


@router.message(F.text == t.BTN_CONTACT)
async def on_contact(message: Message) -> None:
    async with async_session() as session:
        contact = await get_setting(session, "contact_username")
    if not contact:
        await message.answer("📞 Buyurtmani bot orqali bering — admin o'zi bog'lanadi.")
        return
    await message.answer(
        f"📞 Savol yoki buyurtma bo'yicha: @{contact}\nTez javob beramiz 🖤",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="💬 Yozish", url=f"https://t.me/{contact}")]]
        ),
    )


@router.message(F.text == t.BTN_CHANNEL)
async def on_channel(message: Message) -> None:
    async with async_session() as session:
        username = await get_setting(session, "channel_username")
    if not username:
        await message.answer("📢 Kanal tez orada ochiladi. Yangi drop'lar shu yerda bo'ladi 🔥")
        return
    await message.answer(
        f"📢 Yangi drop'lar birinchi kanalda: @{username}",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="📢 Kanalga o'tish", url=f"https://t.me/{username}")]]
        ),
    )


@fallback_router.message(StateFilter(None), F.chat.type == "private")
async def on_unknown(message: Message) -> None:
    user_id = message.from_user.id if message.from_user else 0
    await message.answer("👇 Menyudan tanlang.", reply_markup=await menu_for(user_id))
