import asyncio
import hashlib
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware, Bot, Dispatcher
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.types import MenuButtonWebApp, TelegramObject, Update, WebAppInfo
from aiogram.webhook.aiohttp_server import SimpleRequestHandler
from aiohttp import web
from redis.asyncio import Redis

from .config import settings
from .handlers import router

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("bot")

WEBHOOK_PATH = "/tg/webhook"
DEDUP_TTL = 24 * 3600

Handler = Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]]


class DedupMiddleware(BaseMiddleware):
    """Telegram ретраит webhook, если ответ не пришёл вовремя; при N репликах повтор
    может попасть на другую. SET NX по update_id — апдейт обрабатывается один раз."""

    def __init__(self, redis: Redis) -> None:
        self.redis = redis

    async def __call__(self, handler: Handler, event: TelegramObject, data: dict[str, Any]) -> Any:
        if not isinstance(event, Update):
            return await handler(event, data)
        key = f"tg:update:{event.update_id}"
        if not await self.redis.set(key, 1, nx=True, ex=DEDUP_TTL):
            log.info("duplicate update %s skipped", event.update_id)
            return None
        try:
            return await handler(event, data)
        except Exception:
            await self.redis.delete(key)  # пусть ретрай Telegram повторит
            raise


def build() -> tuple[Bot, Dispatcher, Redis]:
    storage = RedisStorage.from_url(settings.redis_url)
    bot = Bot(settings.bot_token)
    dp = Dispatcher(storage=storage)
    dp.include_router(router)
    dp.update.outer_middleware(DedupMiddleware(storage.redis))
    return bot, dp, storage.redis


async def setup_bot(bot: Bot) -> None:
    await bot.set_chat_menu_button(
        menu_button=MenuButtonWebApp(text="Каталог", web_app=WebAppInfo(url=settings.webapp_url))
    )


async def ensure_webhook(bot: Bot, redis: Redis, allowed_updates: list[str]) -> None:
    """Ставит webhook и кнопку меню ровно одной репликой.

    Если N реплик стартуют разом и все зовут setWebhook, Telegram отвечает flood control
    и реплики падают. Поэтому: webhook уже настроен с этой конфигурацией → ничего не делаем;
    иначе ставит только реплика, взявшая замок в Redis. Секрет getWebhookInfo не отдаёт,
    поэтому факт «настроено с этим секретом» хранится маркером с хэшем конфигурации.
    """
    url = f"{settings.webhook_base_url.rstrip('/')}{WEBHOOK_PATH}"
    config = f"{url}|{settings.webhook_secret}|{','.join(sorted(allowed_updates))}|{settings.webapp_url}"
    marker = f"tg:webhook:{hashlib.sha256(config.encode()).hexdigest()[:16]}"

    info = await bot.get_webhook_info()
    if info.url == url and await redis.exists(marker):
        log.info("webhook already set")
        return
    if not await redis.set("tg:webhook:lock", 1, nx=True, ex=30):
        log.info("webhook is being set by another replica")
        return
    try:
        await bot.set_webhook(url, secret_token=settings.webhook_secret, allowed_updates=allowed_updates)
        await setup_bot(bot)
        await redis.set(marker, 1)
        log.info("webhook set to %s", url)
    finally:
        await redis.delete("tg:webhook:lock")


async def run_webhook() -> None:
    bot, dp, redis = build()
    await ensure_webhook(bot, redis, dp.resolve_used_update_types())

    app = web.Application()
    SimpleRequestHandler(dispatcher=dp, bot=bot, secret_token=settings.webhook_secret).register(app, WEBHOOK_PATH)

    async def health(_: web.Request) -> web.Response:
        await redis.exists("tg:health")  # падает, если Redis недоступен
        return web.json_response({"ok": True})

    app.router.add_get("/health", health)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", settings.port).start()
    log.info("webhook mode on :%s", settings.port)
    try:
        await asyncio.Event().wait()
    finally:
        await runner.cleanup()
        await bot.session.close()
        await redis.aclose()


async def run_polling() -> None:
    bot, dp, redis = build()
    await bot.delete_webhook()
    await setup_bot(bot)
    log.info("polling mode (dev, single replica)")
    try:
        # В сигнатуре start_polling у aiogram нетипизированный sentinel UNSET.
        await dp.start_polling(bot)  # pyright: ignore[reportUnknownMemberType]
    finally:
        await redis.aclose()


if __name__ == "__main__":
    asyncio.run(run_webhook() if settings.webhook_base_url else run_polling())
