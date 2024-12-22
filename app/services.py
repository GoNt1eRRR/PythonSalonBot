import asyncio
from aiogram import Bot


async def schedule_followup(bot: Bot, chat_id: int, delay_seconds: int):
    await asyncio.sleep(delay_seconds)
    try:
        await bot.send_message(
            chat_id,
            "Уже прошло 100 дней с момента вашей процедуры!\n"
            "Не желаете, повторить запись?"
        )
    except Exception as e:
        print("Ошибка при отправке follow-up сообщения:", e)