from datetime import datetime, date, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from config import DATABASE_URL
from models import Base, Client, Order
from data import RENTAL_PRICE_PER_SLOT

engine = create_async_engine(DATABASE_URL, echo=False)
Session = async_sessionmaker(engine, expire_on_commit=False)


async def init_db() -> None:
    """
    Создаёт таблицы, если их ещё нет. Подходит для старта проекта.
    Когда схема начнёт меняться (новые поля, таблицы), лучше перейти
    на Alembic-миграции вместо create_all — они безопаснее для базы,
    в которой уже есть данные.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_or_create_client(tg_user_id: int, tg_username: str | None, full_name: str | None) -> Client:
    """
    Вызывается на /start. Если клиент уже писал боту раньше — просто
    возвращает его (и обновляет имя/username на случай, если поменялись).
    Если нет — создаёт новую запись.
    """
    async with Session() as session:
        client = await session.scalar(select(Client).where(Client.tg_user_id == tg_user_id))
        if client is None:
            client = Client(
                tg_user_id=tg_user_id,
                tg_username=tg_username,
                full_name=full_name,
            )
            session.add(client)
            await session.commit()
            await session.refresh(client)
        else:
            changed = False
            if client.tg_username != tg_username:
                client.tg_username = tg_username
                changed = True
            if full_name and client.full_name != full_name:
                client.full_name = full_name
                changed = True
            if changed:
                await session.commit()
        return client


async def create_order(client_id: int, order_id: str, data: dict) -> Order:
    """
    Создаёт заявку в статусе pending на этапе формирования ссылки на оплату.
    `data` — это тот же словарь, что накапливается в FSMContext по ходу диалога.
    """
    sport = data.get("sport", "tennis")
    category = data.get("category") or sport  # для badminton/pickleball category не задаётся отдельно

    price = data.get("package_price")
    if category == "rent" and price is None:
        price = RENTAL_PRICE_PER_SLOT.get(data.get("rental_duration"))

    booking_date_str = data.get("booking_date")  # ISO-строка "YYYY-MM-DD" из FSM
    booking_date = date.fromisoformat(booking_date_str) if booking_date_str else None
    booking_time = data.get("booking_time")  # строка "HH:MM"

    consent_at_str = data.get("consent_at")  # ISO-строка datetime из FSM
    consent_at = datetime.fromisoformat(consent_at_str) if consent_at_str else None

    async with Session() as session:
        order = Order(
            order_id=order_id,
            client_id=client_id,
            sport=sport,
            category=category,
            lesson_type=data.get("lesson_type"),
            subtype=data.get("subtype"),
            level=data.get("level"),
            location=data.get("location") or data.get("rental_location") or data.get("bp_location"),
            rental_duration=data.get("rental_duration"),
            package_key=data.get("package_key"),
            package_label=data.get("package_label"),
            price=price,
            booking_date=booking_date,
            booking_time=booking_time,
            contact_phone=data.get("client_phone"),
            contact_name=data.get("client_name"),
            consent_given=bool(data.get("consent_given")),
            consent_at=consent_at,
            status="pending",
        )
        session.add(order)
        await session.commit()
        await session.refresh(order)
        return order


async def update_client_contact(client_id: int, phone: str | None, full_name: str | None) -> None:
    """
    Сохраняет актуальные телефон/имя клиента в его профиль (Client) — как
    "последние известные" контактные данные, помимо того что они уже
    зафиксированы в конкретной заявке (Order) на момент записи.
    """
    async with Session() as session:
        client = await session.get(Client, client_id)
        if client is None:
            return
        changed = False
        if phone and client.phone != phone:
            client.phone = phone
            changed = True
        if full_name and client.full_name != full_name:
            client.full_name = full_name
            changed = True
        if changed:
            await session.commit()


async def get_booked_times(location: str, booking_date: date, sport: str = "tennis") -> set[str]:
    """
    Возвращает множество уже занятых времён ("HH:MM") в данной локации на
    указанную дату — среди заявок ЭТОГО ЖЕ вида спорта, которые ещё не
    отменены. Параметр sport важен: в одной локации может быть, например,
    теннисный и бадминтонный корт — их занятость не должна пересекаться.
    """
    async with Session() as session:
        rows = await session.scalars(
            select(Order.booking_time).where(
                Order.location == location,
                Order.booking_date == booking_date,
                Order.sport == sport,
                Order.status != "cancelled",
                Order.booking_time.is_not(None),
            )
        )
        return set(rows.all())


async def mark_order_paid(order_id: str) -> None:
    """
    Помечает заявку оплаченной. Сейчас вызывается по нажатию кнопки
    «Я оплатил(а)» — это временное решение для теста. При подключении
    реального эквайринга сюда же (по order_id) должен приходить вызов
    из webhook-обработчика платёжной системы, а не из хендлера кнопки.
    """
    async with Session() as session:
        order = await session.scalar(select(Order).where(Order.order_id == order_id))
        if order is not None:
            order.status = "paid"
            order.paid_at = datetime.utcnow()
            await session.commit()


# ---------------------------------------------------------------------------
# Отмена записи
# ---------------------------------------------------------------------------

async def get_client_by_tg_id(tg_user_id: int) -> Client | None:
    async with Session() as session:
        return await session.scalar(select(Client).where(Client.tg_user_id == tg_user_id))


async def get_order_by_order_id(order_id: str) -> Order | None:
    async with Session() as session:
        return await session.scalar(select(Order).where(Order.order_id == order_id))


async def get_upcoming_orders(client_id: int) -> list[Order]:
    """
    Предстоящие (ещё не начавшиеся и не отменённые) записи клиента —
    для показа в /cancel. Сортировка по дате/времени.
    """
    today = date.today()
    async with Session() as session:
        rows = await session.scalars(
            select(Order)
            .where(
                Order.client_id == client_id,
                Order.status != "cancelled",
                Order.booking_date.is_not(None),
                Order.booking_date >= today,
            )
            .order_by(Order.booking_date, Order.booking_time)
        )
        return list(rows.all())


async def cancel_order(order_id: str) -> None:
    async with Session() as session:
        order = await session.scalar(select(Order).where(Order.order_id == order_id))
        if order is not None:
            order.status = "cancelled"
            await session.commit()


# ---------------------------------------------------------------------------
# Напоминания за день и за час до занятия/аренды
# ---------------------------------------------------------------------------

async def get_orders_needing_day_reminder() -> list[tuple[Order, Client]]:
    """
    Заявки, для которых пора отправить напоминание «за день» — до начала
    осталось от 23 до 25 часов, оплачено, и напоминание ещё не отправлялось.
    Окно намеренно широкое (2 часа), чтобы не полагаться на идеально точный
    интервал опроса фоновой задачи; от повторной отправки защищает флаг.
    """
    now = datetime.utcnow()
    window_start = now + timedelta(hours=23)
    window_end = now + timedelta(hours=25)
    return await _get_orders_in_window(window_start, window_end, "reminder_day_sent")


async def get_orders_needing_hour_reminder() -> list[tuple[Order, Client]]:
    """То же самое, но окно «за час» — от 45 до 75 минут до начала."""
    now = datetime.utcnow()
    window_start = now + timedelta(minutes=45)
    window_end = now + timedelta(minutes=75)
    return await _get_orders_in_window(window_start, window_end, "reminder_hour_sent")


async def _get_orders_in_window(window_start: datetime, window_end: datetime, flag_column: str) -> list[tuple[Order, Client]]:
    async with Session() as session:
        rows = await session.execute(
            select(Order, Client)
            .join(Client, Order.client_id == Client.id)
            .where(
                Order.status == "paid",
                Order.booking_date.is_not(None),
                Order.booking_date >= window_start.date(),
                Order.booking_date <= window_end.date(),
                Order.booking_time.is_not(None),
                getattr(Order, flag_column).is_(False),
            )
        )
        result = []
        for order, client in rows.all():
            booking_dt = datetime.combine(
                order.booking_date,
                datetime.strptime(order.booking_time, "%H:%M").time(),
            )
            if window_start <= booking_dt <= window_end:
                result.append((order, client))
        return result


async def mark_day_reminder_sent(order_id: str) -> None:
    await _mark_reminder_sent(order_id, "reminder_day_sent")


async def mark_hour_reminder_sent(order_id: str) -> None:
    await _mark_reminder_sent(order_id, "reminder_hour_sent")


async def _mark_reminder_sent(order_id: str, flag_column: str) -> None:
    async with Session() as session:
        order = await session.scalar(select(Order).where(Order.order_id == order_id))
        if order is not None:
            setattr(order, flag_column, True)
            await session.commit()