from aiogram import Router, F
from aiogram.types import Message, FSInputFile
import requests

from app.keyboards import start_keyboard, consent_keyboard
from aiogram.fsm.context import FSMContext

router_start = Router()

BASE_URL = "http://195.133.75.198:8000/api/"


@router_start.message(F.text == "/start")
async def start_command(message: Message, state: FSMContext):
    telegram_id = message.from_user.id
    user_name = message.from_user.first_name

    response = requests.get(f'{BASE_URL}users/', params={"telegram_id": telegram_id})
    if response.status_code == 200:
        users = response.json()
        user = next((u for u in users if u["telegram_id"] == telegram_id), None)
        if user:
            await state.update_data(client_id=user["id"])
            await message.answer(
                f"Рады видеть вас снова, {user_name}! 👋\n\n"
                     "💇‍♀️ Вы можете выбрать салон или любимого мастера\n"
                     "📅 Подобрать удобное время\n"
                     "✨ И записаться на процедуру в несколько кликов!\n\n"
                     "Чем займёмся сегодня? 😊",
                reply_markup=start_keyboard
            )
        else:
            create_response = requests.post(f"{BASE_URL}users/", json={
                "username": user_name,
                "telegram_id": telegram_id
            })
            if create_response.status_code == 201:
                new_user = create_response.json()
                await state.update_data(client_id=new_user["id"])
                await message.answer(
                    f"Вы успешно зарегистрированы, {user_name}! Подтвердите пользовательское соглашение", reply_markup=consent_keyboard
                )

                consent_file = FSInputFile(
                    "app/Agreement.pdf")
                await message.answer_document(document=consent_file)

            else:
                await message.answer("Не удалось автоматически зарегистрировать. Обратитесь к менеджеру")


@router_start.message(F.text == "Я подтверждаю пользовательское соглашение")
async def user_consented(message: Message):
    await message.answer("Спасибо! Добро пожаловать в бота! 🎆\n\n"
        "Теперь вы можете:\n"
        "💇 Записываться на процедуры в лучшие салоны красоты\n"
        "🧑‍🎨 Выбирать любимых мастеров\n"
        "📅 Подбирать удобное время для записи\n\n"
        "Выберите нужный раздел ниже, чтобы начать! 🚀",
        reply_markup=start_keyboard
    )


@router_start.message(F.text == "Связь с Менеджером")
async def start_command(message: Message):
    await message.answer(
        "Если у вас возникли трудности с записью или иные проблемы, то вы можете связаться с менеджером:\n\n"
        'Telegram: @manager\n'
        'Номер телефона: 88005553535\n'
    )


@router_start.message(F.text == "/help")
async def show_help(message: Message):
    await message.answer(
        "ℹ️ *Справка по боту*\n\n"
        "Добро пожаловать в ваш персональный помощник для записи в салоны красоты! 💇‍♀️✨\n\n"
        "Вот что вы можете сделать:\n"
        "1️⃣ *Записаться в Салон*:\n"
        "- Выберите салон\n"
        "- Найдите удобное время и услугу\n"
        "- Получите напоминания о повторной записи через 100 дней\n\n"
        "2️⃣ *Записаться к Мастеру*:\n"
        "- Выберите мастера, с которым вам комфортно\n"
        "- Запишитесь на подходящее время\n"
        "- Получите напоминания о повторной записи через 100 дней\n\n"
        "3️⃣ *Связь с Менеджером*:\n"
        "- Если возникли трудности, смело обращайтесь к нашему менеджеру!\n\n"
        "Выберите нужный пункт меню ниже и наслаждайтесь удобным сервисом! 🚀",
        parse_mode="Markdown",
        reply_markup=start_keyboard
    )

