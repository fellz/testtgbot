import io
import logging

from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandStart, Filter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
    WebAppInfo,
)

from . import api
from .config import settings

log = logging.getLogger(__name__)
router = Router()

CREATE = "Создать товар"
CANCEL = "Отмена"


class IsAdmin(Filter):
    async def __call__(self, message: Message) -> bool:
        return message.from_user is not None and message.from_user.id in settings.admin_ids


class AddProduct(StatesGroup):
    waiting = State()


def catalog_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="Открыть каталог", web_app=WebAppInfo(url=settings.webapp_url)),
    ]])


def admin_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text=CREATE)]], resize_keyboard=True)


def cancel_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text=CANCEL)]], resize_keyboard=True)


async def greet(message: Message) -> None:
    await message.answer("У меня есть товар", reply_markup=catalog_kb())


# --- администратор -------------------------------------------------------------
# Состояние диалога лежит в Redis (RedisStorage), поэтому шаги одного диалога могут
# обработать разные реплики бота.

@router.message(CommandStart(), IsAdmin())
async def admin_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    await greet(message)
    await message.answer(f"Вы администратор. «{CREATE}» — добавить товар.", reply_markup=admin_kb())


@router.message(F.text == CREATE, IsAdmin())
@router.message(Command("create"), IsAdmin())
async def ask_product(message: Message, state: FSMContext) -> None:
    await state.set_state(AddProduct.waiting)
    await message.answer(
        "Пришлите одним сообщением фото товара с подписью — подпись станет названием.",
        reply_markup=cancel_kb(),
    )


@router.message(F.text == CANCEL, IsAdmin())
async def cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Отменено.", reply_markup=admin_kb())


# Фото с подписью от админа принимаем и без нажатия кнопки: сообщение самодостаточно.
@router.message(F.photo, IsAdmin())
async def save_product(message: Message, state: FSMContext, bot: Bot) -> None:
    name = (message.caption or "").strip()
    if not name:
        await message.answer("Нужна подпись к фото — это название товара. Пришлите фото ещё раз с подписью.")
        return
    if len(name) > 200:
        await message.answer("Название длиннее 200 символов — сократите, пожалуйста.")
        return

    if not message.photo:
        return
    photo = message.photo[-1]  # самый большой размер
    buf = io.BytesIO()
    await bot.download(photo, destination=buf)
    try:
        product = await api.create_product(name, buf.getvalue(), f"tg:{message.chat.id}:{message.message_id}")
    except Exception:
        log.exception("create_product failed")
        await message.answer("Не удалось сохранить товар, попробуйте ещё раз.")
        return

    await state.clear()
    await message.answer(f"Товар «{product.name}» добавлен (#{product.id}).", reply_markup=admin_kb())
    await message.answer("Каталог:", reply_markup=catalog_kb())


@router.message(AddProduct.waiting, IsAdmin())
async def wrong_input(message: Message) -> None:
    await message.answer("Жду фото с подписью-названием одним сообщением (или «Отмена»).")


# --- все остальные -------------------------------------------------------------

@router.message()
async def anyone(message: Message) -> None:
    await greet(message)
