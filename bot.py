import asyncio
import logging
import sys
#
import os
#
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

#
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
#
from config import BOT_TOKEN
from handlers import router
from db import init_db
from reminders import reminder_loop

# На Windows asyncio по умолчанию использует ProactorEventLoop, у которого
# есть известный конфликт с asyncpg — соединение с Postgres может обрываться
# посреди handshake с ошибкой ConnectionDoesNotExistError. Переключаемся на
# SelectorEventLoop, с которым asyncpg работает штатно. На Linux/macOS эта
# строка не нужна и не мешает — там уже используется selector-based loop.
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


async def main():
    logging.basicConfig(level=logging.INFO)

    if not BOT_TOKEN or BOT_TOKEN == "PUT_YOUR_TELEGRAM_BOT_TOKEN_HERE":
        raise RuntimeError(
            "Не задан BOT_TOKEN. Установите переменную окружения BOT_TOKEN "
            "или впишите токен в config.py."
        )

    # Создаёт таблицы clients/orders в БД, если их ещё нет.
    await init_db()

    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))

    # MemoryStorage подходит для теста/одного процесса.
    # Для продакшена с несколькими воркерами используйте RedisStorage
    # (aiogram.fsm.storage.redis.RedisStorage), чтобы состояние диалога
    # не терялось при перезапуске и было общим между процессами.
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)

    # Фоновая задача с напоминаниями за день/за час до занятия (см. reminders.py).
    asyncio.create_task(reminder_loop(bot))

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nБот остановлен.")