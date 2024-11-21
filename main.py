import asyncio
import logging

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message
from config import Config, load_config
from logging.handlers import TimedRotatingFileHandler

config: Config = load_config()

# Настройка обработчика логов с ротацией по времени
handler = TimedRotatingFileHandler(
    filename='my_log.log',
    when='midnight',         # Ротация в полночь
    interval=1,              # Частота ротации - раз в сутки
    backupCount=7,           # Сохранять последние 7 файлов логов
    encoding='utf-8'
)
# Форматирование логов
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
handler.setFormatter(formatter)
logging.basicConfig(
    level=logging.DEBUG,
    handlers=[handler]
)

bot = Bot(token=config.tg_bot.token)
dp = Dispatcher()  # получает апдейты и выбирает для них хэндлеры


async def send_log_to_admin(text: str):
    await bot.send_message(config.admin, text)


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
    try:
        username = message.from_user.username
        warning_message = await message.answer(f"@{username}, сообщения с гиперссылками запрещены.")
        await message.delete()
        log_message = f"Удалили сообщение со ссылкой от пользователя {message.from_user.username} ({message.from_user.id}), который писал: {message.text[:100]}"
        logging.info(log_message)
        await send_log_to_admin(log_message)
        await asyncio.create_task(delete_after_delay(warning_message, 30))
    except Exception as e:
        error_message = f"❌ Не удалось удалить сообщение со ссылкой от {message.from_user.username} в чате {message.chat.id}: {e}"
        logging.error(error_message)
        await send_log_to_admin(error_message)

@dp.message(is_read_only)
async def delete_message_from_read_only(message: Message):
    try:
        await message.delete()
        log_message = f"Удалили сообщение от read-only пользователя {message.from_user.username} ({message.from_user.id})"
        logging.info(log_message)
        await send_log_to_admin(log_message)

        warning_message = await message.answer(
            f"@{message.from_user.username}, вам запрещено писать сообщения в этом чате.")
        await asyncio.create_task(delete_after_delay(warning_message, 10))

    except Exception as e:
        error_message = f"❌ Не удалось удалить сообщение от read-only пользователя {message.from_user.username} в чате {message.chat.id}: {e}"
        logging.error(error_message)
        await send_log_to_admin(error_message)


async def delete_after_delay(message: Message, delay: int):
    await asyncio.sleep(delay)
    await message.delete()


async def main():
    # Отключаем webhook, если он используется
    await bot.delete_webhook(drop_pending_updates=True)

    # Запуск polling
    try:
        logging.info("Бот запущен")

        await send_log_to_admin("Бот запущен")

        await dp.start_polling(bot, skip_updates=True, allowed_updates=["message"])
    except Exception as e:
        logging.error(f"Ошибка при поллинге: {e}")
        await send_log_to_admin(f"Ошибка при поллинге: {e}")


if __name__ == '__main__':
    asyncio.run(main())
