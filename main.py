import json
import re
import asyncio
import logging

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message
from config import Config, load_config
from logging.handlers import TimedRotatingFileHandler
from openai import OpenAI

config: Config = load_config()

client = OpenAI(
    api_key=config.openai_token,
)

# Настройка обработчика логов с ротацией по времени
handler = TimedRotatingFileHandler(
    filename='my_log.log',
    when='midnight',  # Ротация в полночь
    interval=1,  # Частота ротации - раз в сутки
    backupCount=7,  # Сохранять последние 7 файлов логов
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

CARD_PATTERN = re.compile(r'(?<!\d)(?:\d[ -]?){12,18}\d(?!\d)')
PHONE_PATTERN = re.compile(
    r'(?<!\d)(?:\+7|8)[ -]?(?:\(\d{3}\)|\d{3})[ -]?\d{3}[ -]?\d{2}[ -]?\d{2}(?!\d)'
)

prompt_template = (
    "Определи, является ли следующий комментарий спамом, особенно с просьбой о переводе денег или предложением работы. "
    "Обоснуй свой ответ одним кратким предложением. "
    "Верни ответ в формате JSON с двумя полями: "
    "'is_spam' (значения: 'да' или 'нет') и 'reason' (обоснование). "
    "Комментарий: {comment}"
)


def sanitize_comment(comment: str) -> str:
    if not isinstance(comment, str):
        return ""

    # Экранируем фигурные скобки
    comment = comment.replace("{", "{{").replace("}", "}}")

    # Удаляем управляющие символы (ASCII 0-31 и 127)
    comment = re.sub(r'[\x00-\x1F\x7F]', '', comment)

    return comment


def extract_json(text: str) -> str | None:
    try:
        # Находим первую открывающуюся и последнюю закрывающуюся фигурную скобку
        start = text.find('{')
        end = text.rfind('}')
        if start != -1 and end != -1 and end > start:
            return text[start:end + 1]
        else:
            return None
    except Exception as e:
        logging.error("Ошибка при извлечении JSON: %s", e)
    return None


def parse_bot_response(api_response: str) -> dict:
    try:
        json_str = extract_json(api_response)
        if not json_str:
            logging.error("Не удалось выделить JSON из ответа.")
            return {}  # можно вернуть None или пустой словарь

        data = json.loads(json_str)

        # Безопасно пытаемся получить необходимые поля
        is_spam = data.get("is_spam")
        reason = data.get("reason")
        return {"is_spam": is_spam, "reason": reason}

    except json.JSONDecodeError as e:
        logging.error("Ошибка декодирования JSON: %s", e)
    except Exception as e:
        logging.error("Ошибка при парсинге ответа: %s", e)

    return {}  # если что-то пошло не так, возвращаем пустой словарь


def get_openai_response(prompt_template: str, comment: str) -> dict:
    try:
        if not prompt_template or not comment:
            logging.error("Неверные входные параметры: prompt_template или comment не заданы")
            return {}

        prompt = prompt_template.format(comment=sanitize_comment(comment))
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            max_tokens=1000,
        )
        result = response.choices[0].message.content.strip()
        return parse_bot_response(result)

    except ValueError as e:
        logging.error(f"Ошибка в структуре ответа: {e}")
        return {}

    except Exception as e:
        logging.error(f"Произошла ошибка при получении завершения чата: {e}")
        return {}


async def send_log_to_admin(text: str):
    await bot.send_message(config.admin, text, parse_mode="MarkdownV2")


def contains_url(message: Message) -> bool:
    if message.entities:
        for entity in message.entities:
            if entity.type in ["url", "text_link"]:
                return True
    return False


def contains_spam(message: Message) -> bool:
    spam_words = ["Тинькофф", "10к в день", "Выплаты", "Выплаты каждый день", "Выплатa ежеднeвнo", "Заработай бабок",
                  "Хочешь заработать деньги?", "Хочешь зарабатывать", "Рaбота с хopoшими условиями",
                  "Ищу курьера", "Требуются курьеры",
                  "Ищу сoтрyдников", "Трeбуются coтрyдники", "Ищу сотрудников", "нeслoжныe задачи",
                  "Bыплаты бeз задeржeк"]

    if message.text:
        for spam_word in spam_words:
            if spam_word in message.text:
                return True

        # номер банковской карты запрещен
        if CARD_PATTERN.search(message.text):
            return True

        # номер телефона - тоже
        if PHONE_PATTERN.search(message.text):
            return True

    return False


def is_read_only(message: Message) -> bool:
    read_only_ids = [6629270937, 5566440515, 6808823109, 6808823109]
    return message.from_user.id in read_only_ids


@dp.message(Command(commands=['ban']))
async def ban_user(message: Message):
    try:
        await bot.ban_chat_member(chat_id=-1002010374304, user_id=5566440515)
        await message.reply(f"Пользователь 5566440515 забанен в канале.")
    except Exception as e:
        await message.reply(f"Произошла ошибка: {e}")


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


@dp.message(contains_spam)
async def delete_spam_message(message: Message):
    try:
        username = message.from_user.username
        warning_message = await message.answer(f"@{username}, ваше сообщение классифицировано как спам.")
        await message.delete()
        log_message = f"! Удалили спам-сообщение от пользователя {message.from_user.username} ({message.from_user.id}), который писал: {message.text[:100]}"
        logging.info(log_message)
        await send_log_to_admin(log_message)
        await asyncio.create_task(delete_after_delay(warning_message, 30))
    except Exception as e:
        error_message = f"❌ Не удалось удалить спам-сообщение от {message.from_user.username} в чате {message.chat.id}: {e}"
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


@dp.message()
async def check_with_openai(message: Message):
    try:
        await send_log_to_admin("Отправляю запрос в OpenAI...")
        result = get_openai_response(prompt_template, message.text)
        if result == {}:
            await send_log_to_admin(f"Ошибка обработки запроса!")
        else:
            verdict = result.get("is_spam", "нет").lower()
            reason = result.get("reason", "Причина не указана")
            await send_log_to_admin(f"**Вердикт:** {verdict}.\n**Пояснение:** {reason}")
            if verdict == "да":
                username = message.from_user.username
                warning_message = await message.answer(f"@{username}, ваше сообщение классифицировано как спам. {reason}")
                await message.delete()
                log_message = f"Удалили спам-сообщение от пользователя {message.from_user.username} ({message.from_user.id}), который писал: {message.text[:100]}. Причина: {reason}"
                logging.info(log_message)
                await send_log_to_admin(log_message)
                await asyncio.create_task(delete_after_delay(warning_message, 30))
    except Exception as e:
        error_message = f"❌ Не удалось удалить спам-сообщение от {message.from_user.username} в чате {message.chat.id}: {e}"
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
