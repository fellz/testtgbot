import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.types import MenuButtonWebApp, Update, WebAppInfo
from aiogram.webhook.aiohttp_server import SimpleRequestHandler
from aiohttp import web
from redis.asyncio import Redis

from .config import settings
from .handlers import router

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("bot")

WEBHOOK_PATH = "/tg/webhook"
DEDUP_TTL = 24 * 3600


def build() -> tuple[Bot, Dispatcher, Redis]:
    redis = Redis.from_url(settings.redis_url)
    bot = Bot(settings.bot_token, default=DefaultBotProperties())
    dp = Dispatcher(storage=RedisStorage(redis))
    dp.include_router(router)

    # Telegram ретраит webhook, если ответ не пришёл вовремя; при N репликах повтор
    # может попасть на другую. SET NX по update_id — апдейт обрабатывается один раз.
    @dp.update.outer_middleware()
    async def dedup(handler, event: Update, data):
        if not await redis.set(f"tg:update:{event.update_id}", 1, nx=True, ex=DEDUP_TTL):
            log.info("duplicate update %s skipped", event.update_id)
            return None
        try:
            return await handler(event, data)
        except Exception:
            await redis.delete(f"tg:update:{event.update_id}")  # пусть ретрай Telegram повторит
            raise

    return bot, dp, redis


async def setup_bot(bot: Bot) -> None:
    await bot.set_chat_menu_button(
        menu_button=MenuButtonWebApp(text="Каталог", web_app=WebAppInfo(url=settings.webapp_url))
    )


async def run_webhook() -> None:
    bot, dp, redis = build()
    # Каждая реплика при старте ставит один и тот же webhook — операция идемпотентна.
    await bot.set_webhook(
        f"{settings.webhook_base_url.rstrip('/')}{WEBHOOK_PATH}",
        secret_token=settings.webhook_secret,
        allowed_updates=dp.resolve_used_update_types(),
    )
    await setup_bot(bot)

    app = web.Application()
    SimpleRequestHandler(dispatcher=dp, bot=bot, secret_token=settings.webhook_secret).register(app, WEBHOOK_PATH)

    async def health(_):
        await redis.ping()
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
        await dp.start_polling(bot)
    finally:
        await redis.aclose()


if __name__ == "__main__":
    asyncio.run(run_webhook() if settings.webhook_base_url else run_polling())
