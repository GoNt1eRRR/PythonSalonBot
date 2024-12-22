import asyncio
from aiogram import Router, F, Bot
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
import requests
from dateutil import parser
from app.services import schedule_followup

router_salon = Router()

BASE_URL = "http://195.133.75.198:8000/api/"


class SalonBookingState(StatesGroup):
    choosing_salon = State()
    choosing_procedure = State()
    choosing_time = State()
    entering_phone = State()


@router_salon.message(F.text == "Записаться в Салон")
async def choose_salon(message: Message, state: FSMContext):
    response = requests.get(f"{BASE_URL}salons/")
    if response.status_code == 200:
        salons = response.json()
        if not salons:
            await message.answer("Список салонов пуст.")
            return

        kb_builder = InlineKeyboardBuilder()
        for salon in salons:
            kb_builder.button(
                text=salon["name"],
                callback_data=f"salon_{salon['id']}"
            )
        kb_builder.adjust(1)

        await message.answer(
            "Выберите салон:",
            reply_markup=kb_builder.as_markup()
        )
        await state.set_state(SalonBookingState.choosing_salon)
    else:
        await message.answer("Ошибка загрузки салонов.")


@router_salon.callback_query(F.data.startswith("salon_"), SalonBookingState.choosing_salon)
async def choose_procedure(callback: CallbackQuery, state: FSMContext):
    salon_id = int(callback.data.split("_")[1])
    await state.update_data(salon_id=salon_id)

    response = requests.get(f"{BASE_URL}procedures/")
    if response.status_code == 200:
        procedures = response.json()
        if not procedures:
            await callback.message.answer("Процедур нет.")
            await callback.answer()
            return

        kb_builder = InlineKeyboardBuilder()
        for procedure in procedures:
            cb_data = f"procedure_salon_{procedure['id']}_{salon_id}"
            text_btn = f"{procedure['name']} ({procedure['price']} руб.)"
            kb_builder.button(text=text_btn, callback_data=cb_data)
        kb_builder.adjust(1)

        await state.set_state(SalonBookingState.choosing_procedure)
        await callback.message.answer(
            "Выберите услугу:",
            reply_markup=kb_builder.as_markup()
        )
        await callback.answer()
    else:
        await callback.message.answer("Ошибка загрузки процедур.")
        await callback.answer()


@router_salon.callback_query(F.data.startswith("procedure_salon_"), SalonBookingState.choosing_procedure)
async def choose_time(callback: CallbackQuery, state: FSMContext):
    _, _, proc_id_str, salon_id_str = callback.data.split("_", maxsplit=3)
    procedure_id = int(proc_id_str)
    salon_id = int(salon_id_str)

    await state.update_data(procedure_id=procedure_id, salon_id=salon_id)

    response = requests.get(
        f"{BASE_URL}availabilities/",
        params={"procedure_id": procedure_id, "salon_id": salon_id}
    )
    if response.status_code == 200:
        slots = response.json()
        slots = [s for s in slots if not s["is_booked"]]
        slots = [s for s in slots if s["salon"]["id"] == salon_id]

        filtered_slots = []
        for s in slots:
            master_procedure_ids = [p["id"] for p in s["specialist"]["procedures"]]
            if procedure_id in master_procedure_ids:
                filtered_slots.append(s)

        if not slots:
            await callback.message.answer("Нет доступных слотов в этом салоне.")
            await callback.answer()
            return

        kb_builder = InlineKeyboardBuilder()
        for slot in filtered_slots:
            slot_id = slot["id"]
            start_iso = slot["start_time"]
            end_iso = slot["end_time"]

            start_dt = parser.isoparse(start_iso)
            end_dt = parser.isoparse(end_iso)

            start_str = start_dt.strftime("%d.%m.%Y %H:%M")
            end_str = end_dt.strftime("%H:%M")

            master_name = slot["specialist"]["user"]["username"]

            cb_data = f"slot_salon_{slot_id}"
            text_btn = f"{start_str} - {end_str} | Мастер: {master_name}"
            kb_builder.button(text=text_btn, callback_data=cb_data)
        kb_builder.adjust(1)

        await state.set_state(SalonBookingState.choosing_time)
        await callback.message.answer(
            "Выберите время:",
            reply_markup=kb_builder.as_markup()
        )
        await callback.answer()
    else:
        await callback.message.answer("Ошибка загрузки времени.")
        await callback.answer()


@router_salon.callback_query(F.data.startswith("slot_salon_"), SalonBookingState.choosing_time)
async def ask_phone(callback: CallbackQuery, state: FSMContext):
    slot_id_str = callback.data.split("_")[2]
    slot_id = int(slot_id_str)
    await state.update_data(slot_id=slot_id)

    await state.set_state(SalonBookingState.entering_phone)
    await callback.message.answer("Введите ваш номер телефона:")
    await callback.answer()


@router_salon.message(SalonBookingState.entering_phone)
async def finalize_booking(message: Message, state: FSMContext):
    phone_number = message.text
    data = await state.get_data()

    if "client_id" not in data:
        telegram_id = message.from_user.id
        user_name = message.from_user.first_name

        response = requests.get(f'{BASE_URL}users/', params={"telegram_id": telegram_id})
        if response.status_code == 200:
            users = response.json()
            user = next((u for u in users if u["telegram_id"] == telegram_id), None)
            if user:
                await state.update_data(client_id=user["id"])
            else:
                create_response = requests.post(f'{BASE_URL}users/', json={
                    "username": user_name,
                    "telegram_id": telegram_id,
                    "role": "client"
                })
                if create_response.status_code == 201:
                    new_user = create_response.json()
                    await state.update_data(client_id=new_user["id"])
                else:
                    await message.answer("Ошибка регистрации. Попробуйте /start.")
                    return
        else:
            await message.answer("Ошибка при проверке пользователя. Попробуйте /start.")
            return

    data = await state.get_data()
    client_id = data.get("client_id")

    booking_data = {
        "client_id": client_id,
        "salon_id": data["salon_id"],
        "procedure_id": data["procedure_id"],
        "availability_id": data["slot_id"],
        "phone_number": phone_number
    }
    response = requests.post(f'{BASE_URL}bookings/', json=booking_data)
    if response.status_code == 201:
        resp_data = response.json()
        salon_info = resp_data["salon"]
        procedure_info = resp_data["procedure"]
        avail_info = resp_data["availability"]
        start_time = avail_info["start_time"]
        end_time = avail_info["end_time"]
        master_name = avail_info["specialist"]["user"]["username"]

        start_dt = parser.isoparse(start_time)
        end_dt = parser.isoparse(end_time)

        start_str = start_dt.strftime("%d.%m.%Y %H:%M")
        end_str = end_dt.strftime("%H:%M")

        msg_text = (
            f"Запись успешно создана!\n\n"
            f"Салон: {salon_info['name']} ({salon_info['address']})\n"
            f"Услуга: {procedure_info['name']} (Цена: {procedure_info['price']})\n"
            f"Мастер: {master_name}\n"
            f"Время: {start_str} - {end_str}\n\n"
            "За час до процедуры с вами свяжется менеджер для подтверждения записи.\n"
            "Спасибо, что выбрали нас!"
        )

        await message.answer(msg_text)
        await state.update_data(salon_id=None, procedure_id=None, slot_id=None)

        bot: Bot = message.bot
        await asyncio.create_task(schedule_followup(bot, message.chat.id, 120))
    else:
        print(f"Ошибка создания записи: {response.status_code} - {response.text}")
        await message.answer("Ошибка создания записи. Попробуйте снова.")
