import asyncio
import logging

from aiogram import Bot

from data import build_reminder_text
from db import (
    get_orders_needing_day_reminder,
    get_orders_needing_hour_reminder,
    mark_day_reminder_sent,
    mark_hour_reminder_sent,
)

log = logging.getLogger(__name__)

CHECK_INTERVAL_SECONDS = 300  # проверяем базу раз в 5 минут


async def reminder_loop(bot: Bot) -> None:
    """
    Фоновая задача: раз в CHECK_INTERVAL_SECONDS секунд проверяет базу и
    отправляет клиентам напоминания за день и за час до занятия/аренды.

    Работает, пока жив процесс бота. При перезапуске бота просто продолжает
    с того же места — флаги reminder_day_sent/reminder_hour_sent в БД не
    дают напоминанию отправиться повторно.

    Ограничение (MVP): если бот был выключен дольше, чем ширина окна
    проверки (см. get_orders_needing_day_reminder/hour_reminder в db.py),
    какое-то напоминание можно пропустить — это принято как разумный
    компромисс для простоты реализации.
    """
    while True:
        try:
            for order, client in await get_orders_needing_day_reminder():
                await _send_reminder(bot, order, client, "day")
                await mark_day_reminder_sent(order.order_id)

            for order, client in await get_orders_needing_hour_reminder():
                await _send_reminder(bot, order, client, "hour")
                await mark_hour_reminder_sent(order.order_id)
        except Exception:
            log.exception("Ошибка в фоновой задаче напоминаний")

        await asyncio.sleep(CHECK_INTERVAL_SECONDS)


async def _send_reminder(bot: Bot, order, client, kind: str) -> None:
    text = build_reminder_text(order, kind)
    try:
        await bot.send_message(client.tg_user_id, text)
    except Exception:
        # Например, клиент заблокировал бота — не роняем всю фоновую задачу.
        log.exception(
            "Не удалось отправить напоминание клиенту tg_id=%s (заказ %s)",
            client.tg_user_id, order.order_id,
        )