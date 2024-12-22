import asyncio
from aiogram import Router, F, Bot
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
import requests
from app.services import schedule_followup

from dateutil import parser

router_master = Router()

BASE_URL = "http://195.133.75.198:8000/api/"


class MasterBookingState(StatesGroup):
    choosing_master = State()
    choosing_procedure = State()
    choosing_time = State()
    entering_phone = State()


@router_master.message(F.text == "Записаться к Мастеру")
async def choose_master(message: Message, state: FSMContext):
    response = requests.get(f"{BASE_URL}specialists/")
    if response.status_code == 200:
        specialists = response.json()
        if not specialists:
            await message.answer("К сожалению, пока нет доступных мастеров.")
            return

        kb_builder = InlineKeyboardBuilder()
        for specialist in specialists:
            spec_id = specialist["id"]
            name = specialist["user"]["username"]
            kb_builder.button(text=name, callback_data=f"master_{spec_id}")
        kb_builder.adjust(1)

        await message.answer("Выберите мастера:", reply_markup=kb_builder.as_markup())
        await state.set_state(MasterBookingState.choosing_master)
    else:
        await message.answer("Ошибка загрузки мастеров.")


@router_master.callback_query(F.data.startswith("master_"), MasterBookingState.choosing_master)
async def choose_procedure_for_master(callback: CallbackQuery, state: FSMContext):
    master_id = int(callback.data.split("_")[1])
    await state.update_data(master_id=master_id)

    response = requests.get(f"{BASE_URL}specialists/{master_id}/")
    if response.status_code == 200:
        specialist = response.json()
        procedures = specialist["procedures"]
        if not procedures:
            await callback.message.answer("У этого мастера нет доступных процедур.")
            await callback.answer()
            return

        kb_builder = InlineKeyboardBuilder()
        for procedure in procedures:
            cb_data = f"procedure_master_{procedure['id']}"
            text_btn = f"{procedure['name']} ({procedure['price']} руб.)"
            kb_builder.button(text=text_btn, callback_data=cb_data)
        kb_builder.adjust(1)

        await state.set_state(MasterBookingState.choosing_procedure)
        await callback.message.answer("Выберите процедуру:", reply_markup=kb_builder.as_markup())
        await callback.answer()
    else:
        await callback.message.answer("Ошибка получения данных мастера.")
        await callback.answer()


@router_master.callback_query(F.data.startswith("procedure_master_"), MasterBookingState.choosing_procedure)
async def choose_time_for_master(callback: CallbackQuery, state: FSMContext):

    procedure_id = int(callback.data.split("_")[2])  # "procedure_master_XXX"
    data = await state.get_data()
    master_id = data["master_id"]

    await state.update_data(procedure_id=procedure_id)

    response = requests.get(
        f"{BASE_URL}availabilities/",
        params={"specialist_id": master_id, "procedure_id": procedure_id}
    )
    if response.status_code == 200:
        slots = response.json()
        free_slots = [s for s in slots if not s["is_booked"]]
        free_slots = [s for s in free_slots if s["specialist"]["id"] == master_id]

        if not free_slots:
            await callback.message.answer("Нет свободных слотов у этого мастера для выбранной процедуры.")
            await callback.answer()
            return

        kb_builder = InlineKeyboardBuilder()
        for slot in free_slots:
            slot_id = slot["id"]
            salon_name = slot["salon"]["name"]

            start_iso = slot["start_time"]
            end_iso = slot["end_time"]

            start_dt = parser.isoparse(start_iso)
            end_dt = parser.isoparse(end_iso)
            start_str = start_dt.strftime("%d.%m.%Y %H:%M")
            end_str = end_dt.strftime("%H:%M")

            text_btn = f"{start_str} - {end_str} | Салон: {salon_name}"
            cb_data = f"slot_master_{slot_id}"
            kb_builder.button(text=text_btn, callback_data=cb_data)
        kb_builder.adjust(1)

        await state.set_state(MasterBookingState.choosing_time)
        await callback.message.answer("Выберите подходящее время:", reply_markup=kb_builder.as_markup())
        await callback.answer()
    else:
        await callback.message.answer("Ошибка загрузки слотов.")
        await callback.answer()


@router_master.callback_query(F.data.startswith("slot_master_"), MasterBookingState.choosing_time)
async def ask_phone_master(callback: CallbackQuery, state: FSMContext):
    slot_id = int(callback.data.split("_")[2])

    response_slot = requests.get(f"{BASE_URL}availabilities/{slot_id}/")
    if response_slot.status_code == 200:
        slot_data = response_slot.json()
        salon_id = slot_data["salon"]["id"]

        await state.update_data(slot_id=slot_id, salon_id=salon_id)
    else:
        await callback.message.answer("Ошибка при получении данных о слоте.")
        await callback.answer()
        return

    await state.set_state(MasterBookingState.entering_phone)
    await callback.message.answer("Введите ваш номер телефона:")
    await callback.answer()


@router_master.message(MasterBookingState.entering_phone)
async def finalize_master_booking(message: Message, state: FSMContext):
    phone_number = message.text
    data = await state.get_data()

    client_id = data.get("client_id")
    if not client_id:
        telegram_id = message.from_user.id
        user_name = message.from_user.first_name
        response = requests.get(f"{BASE_URL}users/", params={"telegram_id": telegram_id})
        if response.status_code == 200:
            users = response.json()
            user = next((u for u in users if u["telegram_id"] == telegram_id), None)
            if user:
                client_id = user["id"]
                await state.update_data(client_id=client_id)
            else:
                create_response = requests.post(f"{BASE_URL}users/", json={
                    "username": user_name,
                    "telegram_id": telegram_id,
                    "role": "client"
                })
                if create_response.status_code == 201:
                    new_user = create_response.json()
                    client_id = new_user["id"]
                    await state.update_data(client_id=client_id)
                else:
                    await message.answer("Ошибка при регистрации. Попробуйте /start.")
                    return
        else:
            await message.answer("Ошибка при проверке пользователя. Попробуйте /start.")
            return

    slot_id = data["slot_id"]
    salon_id = data["salon_id"]

    booking_data = {
        "client_id": client_id,
        "salon_id": salon_id,
        "procedure_id": data["procedure_id"],
        "availability_id": slot_id,
        "phone_number": phone_number
    }
    response = requests.post(f"{BASE_URL}bookings/", json=booking_data)
    if response.status_code == 201:
        new_booking = response.json()

        salon_info = new_booking["salon"]
        procedure_info = new_booking["procedure"]
        availability_info = new_booking["availability"]
        master_name = availability_info["specialist"]["user"]["username"]

        start_iso = availability_info["start_time"]
        end_iso = availability_info["end_time"]

        start_dt = parser.isoparse(start_iso)
        end_dt = parser.isoparse(end_iso)

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
        await state.update_data(master_id=None, procedure_id=None, slot_id=None)
        await state.set_state(None)

        bot: Bot = message.bot
        await asyncio.create_task(schedule_followup(bot, message.chat.id, 120))
    else:
        await message.answer(f'Ошибка при записи: {response.status_code}, пожалуйста, нажмите "выбрать мастера" еще раз')
