from dataclasses import dataclass

from environs import Env


@dataclass
class TgBot:
    token: str  # Токен для доступа к телеграм-боту


@dataclass
class Config:
    tg_bot: TgBot
    admin: int
    read_only: dict[int]
    openai_token: str

# Создаем функцию, которая будет читать файл .env и возвращать экземпляр
# класса Config с заполненными полями token и admin_ids
def load_config(path: str | None = None) -> Config:
    env = Env()
    env.read_env(path)
    read_only = env.list('READ_ONLY', subcast=int)  # Преобразуем строку в список целых чисел
    return Config(tg_bot=TgBot(token=env('API_TOKEN')),
                  admin=env('ADMIN'),
                  read_only=read_only,
                  openai_token=env('OPENAI_KEY'))
