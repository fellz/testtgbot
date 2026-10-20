from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode


class Settings(BaseSettings):
    bot_token: str
    # Telegram ID администраторов через запятую: 123,456
    admin_ids: Annotated[frozenset[int], NoDecode] = frozenset()
    redis_url: str = "redis://redis:6379/0"
    # Внутренний адрес API (через балансировщик) и общий токен для создания товаров.
    api_url: str = "http://lb/api"
    internal_token: str = "change-me"
    # Публичный адрес Mini App (HTTPS) — его открывает кнопка в боте.
    webapp_url: str = "https://example.com/"
    # Пусто → long polling (только для локальной разработки, ОДНА реплика).
    # Задан → webhook на <base>/tg/webhook; так бот масштабируется на N реплик.
    webhook_base_url: str = ""
    webhook_secret: str = "change-me-too"
    port: int = 8080

    @field_validator("admin_ids", mode="before")
    @classmethod
    def split_ids(cls, v: object) -> object:
        if isinstance(v, str):
            return frozenset(int(x) for x in v.replace(" ", "").split(",") if x)
        return v


# Обязательные поля (bot_token) приходят из окружения — pyright этого не видит.
settings = Settings()  # pyright: ignore[reportCallIssue]
