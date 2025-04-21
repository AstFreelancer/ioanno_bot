from dataclasses import dataclass, field
from typing import List
import os
import logging

from environs import Env
from PIL import Image
import imagehash

def _load_forbidden_hashes(path: str) -> List[imagehash.ImageHash]:
    """
    Сканирует директорию path и возвращает список phash для каждого
    допустимого файла-изображения.
    """
    hashes: List[imagehash.ImageHash] = []
    if not os.path.isdir(path):
        logging.warning(f"Каталог forbidden_images не найден: {path}")
        return hashes

    for fname in os.listdir(path):
        full = os.path.join(path, fname)
        if not os.path.isfile(full):
            continue
        try:
            with Image.open(full) as img:
                hashes.append(imagehash.phash(img))
        except Exception as e:
            logging.error(f"Не удалось обработать {fname} в {path}: {e}")
    logging.info(f"Загружено {len(hashes)} хешей запрещённых изображений из {path}")
    return hashes

@dataclass
class TgBot:
    token: str  # Токен для доступа к телеграм-боту


@dataclass
class Config:
    tg_bot: TgBot
    admin: int
    read_only: dict[int]
    openai_token: str
    channel_id: int
    forbidden_images_path: str = "forbidden_images"
    hash_threshold: int = 5
    forbidden_hashes: List[imagehash.ImageHash] = field(init=False, default_factory=list)

# Создаем функцию, которая будет читать файл .env и возвращать экземпляр
# класса Config с заполненными полями token и admin_ids
def load_config(path: str | None = None) -> Config:
    env = Env()
    env.read_env(path)
    read_only = env.list('READ_ONLY', subcast=int)  # Преобразуем строку в список целых чисел
    cfg = Config(tg_bot=TgBot(token=env('API_TOKEN')),
                  admin=env('ADMIN'),
                  read_only=read_only,
                  openai_token=env('OPENAI_KEY'),
                  channel_id=int(env('CHANNEL_ID')),
                  forbidden_images_path=env.str('FORBIDDEN_IMAGES_PATH', 'forbidden_images'),
                  hash_threshold=env.int('HASH_THRESHOLD', 5)
                  )
    cfg.forbidden_hashes = _load_forbidden_hashes(cfg.forbidden_images_path)

    return cfg