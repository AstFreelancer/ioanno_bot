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


def is_read_only(message: Message) -> bool:
    return message.from_user.id in config.read_only


@dp.message(contains_url)
async def delete_message_with_url(message: Message):
    username = message.from_user.username
    await message.delete()
    warning_message = await message.answer(f"@{username}, сообщения с гиперссылками запрещены.")
    await asyncio.create_task(delete_after_delay(warning_message, 30))

@dp.message(is_read_only)
async def delete_message_from_read_only(message: Message):
    text = message.text[:30]
    logging.info(f"Удалили сообщение от пользователя {message.from_user.username} ({message.from_user.id}), который писал: {text}")
    await message.delete()

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

    await bot.unban_chat_member(-1002221193642, 7320802156)
    logging.info(f"Пользователь 7320802156 разблокирован.")

if __name__ == '__main__':
    asyncio.run(main())
