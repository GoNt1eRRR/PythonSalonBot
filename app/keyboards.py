from aiogram.types import ReplyKeyboardMarkup, KeyboardButton


consent_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Я подтверждаю пользовательское соглашение")]
    ],
    resize_keyboard=True
)


start_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Записаться в Салон")],
        [KeyboardButton(text="Записаться к Мастеру")],
        [KeyboardButton(text="Связь с Менеджером")],
    ],
    resize_keyboard=True
)
