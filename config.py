import os

# Токен бота, полученный у @BotFather.
# Проще всего задать через переменную окружения BOT_TOKEN,
# но для быстрого теста можно вписать строкой прямо сюда.
BOT_TOKEN = os.getenv("BOT_TOKEN", "8638688048:AAG89_qSTOz4d16oTOHpDbobU8bU24D3RxU")

# ID администраторов (через запятую в переменной окружения ADMIN_IDS),
# которым будут приходить уведомления о новых записях.
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]

# Базовый URL для формирования ссылки на оплату.
# Сейчас это заглушка — просто генерируется ссылка с order_id в параметре.
# Когда подключите реальный эквайринг (ЮKassa/Tinkoff/CloudPayments),
# замените generate_payment_link() в data.py на реальный вызов их API.
PAYMENT_BASE_URL = os.getenv("PAYMENT_BASE_URL", "https://pay.tenniscapital.ru/pay")

# Строка подключения к PostgreSQL.
# Формат: postgresql+asyncpg://user:password@host:port/dbname
# Порт 5433 (не 5432!) — потому что на этой машине 5432 уже занят другим,
# локально установленным Postgres. Контейнер из docker-compose.yml проброшен
# именно на 5433, чтобы не конфликтовать с ним.
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://bot:bot@localhost:5433/tenniscapital",
)
