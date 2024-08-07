import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.types import Message
from config import Config, load_config

config: Config = load_config()

logging.basicConfig(level=logging.INFO)

bot = Bot(token=config.tg_bot.token)
dp = Dispatcher()  # получает апдейты и выбирает для них хэндлеры

def contains_url(message: Message) -> bool:
    if message.entities:
        for entity in message.entities:
            if entity.type in ["url", "text_link"]:
                return True
    return False

@dp.message(contains_url)
async def delete_message_with_url(message: Message):
    username = message.from_user.username
    await message.delete()
    warning_message = await message.answer(f"@{username}, сообщения с гиперссылками запрещены.")
    asyncio.create_task(delete_after_delay(warning_message, 30))

async def delete_after_delay(message: Message, delay: int):
    await asyncio.sleep(delay)
    await message.delete()
async def main():
    # Отключаем webhook, если он используется
    await bot.delete_webhook(drop_pending_updates=True)

    # Запуск polling
    try:
        await dp.start_polling(bot, skip_updates=True, allowed_updates=["message"])
    except Exception as e:
        logging.error(f"Ошибка при поллинге: {e}")

if __name__ == '__main__':
    asyncio.run(main())
