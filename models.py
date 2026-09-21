from datetime import datetime, date

from sqlalchemy import BigInteger, String, Integer, DateTime, Date, Boolean, ForeignKey
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Client(Base):
    """
    Клиент бота. Один клиент — одна запись, вне зависимости от того,
    сколько раз он записывался на занятия или арендовал корт.

    Поле phone сделано nullable и вынесено отдельно намеренно: сейчас бот
    его не запрашивает, но когда понадобится сверять клиентов бота со
    старой базой предприятия (клиенты, которые были до бота), это будет
    ключ для сопоставления — просто начнём его заполнять, схему менять
    не придётся.
    """
    __tablename__ = "clients"

    id: Mapped[int] = mapped_column(primary_key=True)
    tg_user_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    tg_username: Mapped[str | None] = mapped_column(String, nullable=True)
    full_name: Mapped[str | None] = mapped_column(String, nullable=True)
    phone: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    orders: Mapped[list["Order"]] = relationship(back_populates="client")


class Order(Base):
    """
    Одна заявка/запись клиента: на школу (детская/взрослая) или на аренду корта.
    Создаётся в статусе "pending" в момент формирования ссылки на оплату,
    переводится в "paid" после подтверждения оплаты.
    """
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[str] = mapped_column(String, unique=True, index=True)

    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"))
    client: Mapped["Client"] = relationship(back_populates="orders")

    # sport: "tennis" / "badminton" / "pickleball" — используется отдельно от
    # category для проверки занятости слота, чтобы разные виды спорта в одной
    # локации не мешали друг другу (у них разные физические корты).
    sport: Mapped[str] = mapped_column(String, default="tennis")
    category: Mapped[str] = mapped_column(String)  # kids / adults / rent / badminton / pickleball
    lesson_type: Mapped[str | None] = mapped_column(String, nullable=True)  # group / personal
    subtype: Mapped[str | None] = mapped_column(String, nullable=True)
    level: Mapped[str | None] = mapped_column(String, nullable=True)
    location: Mapped[str | None] = mapped_column(String, nullable=True)
    rental_duration: Mapped[str | None] = mapped_column(String, nullable=True)
    package_key: Mapped[str | None] = mapped_column(String, nullable=True)
    package_label: Mapped[str | None] = mapped_column(String, nullable=True)
    price: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Дата и время записи. booking_time хранится строкой "HH:MM" — так проще
    # сравнивать занятые слоты, без возни с часовыми поясами.
    booking_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    booking_time: Mapped[str | None] = mapped_column(String, nullable=True)

    # Контакт и согласие, собранные непосредственно в этой заявке — хранятся
    # здесь (а не только в Client), чтобы у каждой конкретной записи было
    # своё подтверждение согласия на момент оформления (для истории/сверки),
    # даже если контактные данные клиента потом изменятся.
    contact_phone: Mapped[str | None] = mapped_column(String, nullable=True)
    contact_name: Mapped[str | None] = mapped_column(String, nullable=True)
    consent_given: Mapped[bool] = mapped_column(Boolean, default=False)
    consent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Напоминания за день/за час — флаги нужны, чтобы фоновая задача не
    # отправляла одно и то же уведомление повторно при каждом новом проходе.
    reminder_day_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    reminder_hour_sent: Mapped[bool] = mapped_column(Boolean, default=False)

    status: Mapped[str] = mapped_column(String, default="pending")  # pending / paid / cancelled
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)