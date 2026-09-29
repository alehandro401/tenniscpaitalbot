"""
Оплата через встроенный платёжный API Telegram (метод sendInvoice),
подключённый к ЮKassa через @BotFather. Это не отдельный REST-клиент —
Telegram сам показывает форму оплаты внутри чата и сам присылает боту
подтверждение (PreCheckoutQuery, затем SuccessfulPayment), см. handlers.py.

Инструкция по получению YOOKASSA_PROVIDER_TOKEN:
https://yookassa.ru/docs/support/payments/onboarding/integration/cms-module/telegram

Если токен не задан — бот работает в старом тестовом режиме (см. handlers.py:
фейковая ссылка + кнопка ручной проверки, без реального провайдера).
"""
from config import YOOKASSA_PROVIDER_TOKEN


def is_yookassa_configured() -> bool:
    return bool(YOOKASSA_PROVIDER_TOKEN)