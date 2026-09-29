import os

# Токен бота, полученный у @BotFather.
# Проще всего задать через переменную окружения BOT_TOKEN,
# но для быстрого теста можно вписать строкой прямо сюда.
BOT_TOKEN = os.getenv("BOT_TOKEN", "8638688048:AAG89_qSTOz4d16oTOHpDbobU8bU24D3RxU")

# ID администраторов (через запятую в переменной окружения ADMIN_IDS),
# которым будут приходить уведомления о новых записях.
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]

# Базовый URL для формирования ссылки на оплату.
# Используется ТОЛЬКО как запасной вариант (тестовый режим), если ключи
# ЮKassa ниже не заданы — тогда бот работает как раньше, без реальных денег.
PAYMENT_BASE_URL = os.getenv("PAYMENT_BASE_URL", "https://pay.tenniscapital.ru/pay")
 
# ---------------------------------------------------------------------------
# ЮKassa — приём платежей прямо внутри Telegram (встроенный Payments API
# Telegram, sendInvoice). Инструкция по получению токена:
# https://yookassa.ru/docs/support/payments/onboarding/integration/cms-module/telegram
#   1. В @BotFather: /mybots → выбрать бота → Payments →
#      "Connect ЮKassa: тест" (для теста) или "Connect ЮKassa: платежи" (реально).
#   2. Авторизоваться в открывшемся диалоге с ботом ЮKassa, выдать доступ.
#   3. @BotFather пришлёт payment provider token — это и есть значение ниже
#      (НЕ путать с BOT_TOKEN — это два разных токена).
# Если не задано — бот работает в старом тестовом режиме (фейковая ссылка +
# кнопка ручной проверки, без реального провайдера).
# ---------------------------------------------------------------------------
YOOKASSA_PROVIDER_TOKEN = os.getenv("YOOKASSA_PROVIDER_TOKEN", "")
 
# Строка подключения к PostgreSQL.
# Формат: postgresql+asyncpg://user:password@host:port/dbname
# Порт 5433 (не 5432!) — потому что на этой машине 5432 уже занят другим,
# локально установленным Postgres. Контейнер из docker-compose.yml проброшен
# именно на 5433, чтобы не конфликтовать с ним.
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://bot:bot@localhost:5433/tenniscapital",
)
