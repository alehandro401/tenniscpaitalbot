from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

from data import (
    CATEGORY_LABELS,
    LESSON_TYPE_LABELS,
    GROUP_SUBTYPES,
    PERSONAL_SUBTYPES,
    LEVEL_LABELS,
    LOCATIONS,
    SPORT_LABELS,
)


def kb_sport() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for key, label in SPORT_LABELS.items():
        b.button(text=label, callback_data=f"sport:{key}")
    b.adjust(1)
    return b.as_markup()


def kb_category(back_target: str = "back:sport") -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for key, label in CATEGORY_LABELS.items():
        b.button(text=label, callback_data=f"cat:{key}")
    b.adjust(1)
    b.row(InlineKeyboardButton(text="◀️ Назад", callback_data=back_target))
    return b.as_markup()


def kb_lesson_type() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for key, label in LESSON_TYPE_LABELS.items():
        b.button(text=label, callback_data=f"ltype:{key}")
    b.button(text="◀️ Назад", callback_data="back:category")
    b.adjust(1)
    return b.as_markup()


def kb_group_subtype() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for key, label in GROUP_SUBTYPES.items():
        b.button(text=label, callback_data=f"group:{key}")
    b.button(text="◀️ Назад", callback_data="back:lesson_type")
    b.adjust(1)
    return b.as_markup()


def kb_personal_subtype() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for key, label in PERSONAL_SUBTYPES.items():
        b.button(text=label, callback_data=f"personal:{key}")
    b.button(text="◀️ Назад", callback_data="back:lesson_type")
    b.adjust(1)
    return b.as_markup()


def kb_level(back_target: str = "back:subtype") -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for key, label in LEVEL_LABELS.items():
        b.button(text=label, callback_data=f"level:{key}")
    b.button(text="◀️ Назад", callback_data=back_target)
    b.adjust(1)
    return b.as_markup()


def kb_locations(locations: list[str] | None = None, prefix: str = "loc", back_target: str = "back:level") -> InlineKeyboardMarkup:
    """По умолчанию — полный список локаций тенниса (LOCATIONS). Для бадминтона/
    пиклбола передавайте свой (более короткий) список через параметр locations."""
    b = InlineKeyboardBuilder()
    for idx, loc in enumerate(locations if locations is not None else LOCATIONS):
        b.button(text=loc, callback_data=f"{prefix}:{idx}")
    b.adjust(2)
    b.row(InlineKeyboardButton(text="◀️ Назад", callback_data=back_target))
    return b.as_markup()


def kb_options(options: dict, prefix: str, back_target: str) -> InlineKeyboardMarkup:
    """Универсальная клавиатура вида {ключ: подпись} -> кнопки prefix:ключ."""
    b = InlineKeyboardBuilder()
    for key, label in options.items():
        b.button(text=label, callback_data=f"{prefix}:{key}")
    b.adjust(1)
    b.row(InlineKeyboardButton(text="◀️ Назад", callback_data=back_target))
    return b.as_markup()


def kb_rental_complexes(complexes: list[tuple[str, str]], back_target: str) -> InlineKeyboardMarkup:
    """complexes: список (key, название) — например data.get_rental_complexes()."""
    b = InlineKeyboardBuilder()
    for key, name in complexes:
        b.button(text=name, callback_data=f"rcx:{key}")
    b.adjust(1)
    b.row(InlineKeyboardButton(text="◀️ Назад", callback_data=back_target))
    return b.as_markup()


def kb_courts(courts: list[tuple[str, str]], prefix: str, back_target: str) -> InlineKeyboardMarkup:
    """courts: список (key, название корта). Используется и для тенниса, и для бадминтона."""
    b = InlineKeyboardBuilder()
    for key, name in courts:
        b.button(text=name, callback_data=f"{prefix}:{key}")
    b.adjust(1)
    b.row(InlineKeyboardButton(text="◀️ Назад", callback_data=back_target))
    return b.as_markup()


def kb_packages(packages: list[tuple[str, str, int]], prefix: str, back_target: str) -> InlineKeyboardMarkup:
    """packages: список (key, label, price) — например data.GROUP_PACKAGES."""
    b = InlineKeyboardBuilder()
    for key, label, price in packages:
        b.button(text=f"{label} — {price} ₽", callback_data=f"{prefix}:{key}")
    b.adjust(1)
    b.row(InlineKeyboardButton(text="◀️ Назад", callback_data=back_target))
    return b.as_markup()


def kb_offer_formats(offers: list[dict], back_target: str) -> InlineKeyboardMarkup:
    """Выбор формата групповых занятий, когда в локации их несколько (обычная/мини-группа/кардио)."""
    b = InlineKeyboardBuilder()
    for offer in offers:
        b.button(text=offer["title"], callback_data=f"offerfmt:{offer['key']}")
    b.adjust(1)
    b.row(InlineKeyboardButton(text="◀️ Назад", callback_data=back_target))
    return b.as_markup()


def kb_dates(dates: list, labels: list[str], prefix: str, back_target: str) -> InlineKeyboardMarkup:
    """dates — список дат (используются их индексы в callback_data), labels — подписи для кнопок."""
    b = InlineKeyboardBuilder()
    for idx, label in enumerate(labels):
        b.button(text=label, callback_data=f"{prefix}:{idx}")
    b.adjust(2)
    b.row(InlineKeyboardButton(text="◀️ Назад", callback_data=back_target))
    return b.as_markup()


def kb_times(times: list[str], prefix: str, back_target: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for t in times:
        b.button(text=t, callback_data=f"{prefix}:{t}")
    b.adjust(3)
    b.row(InlineKeyboardButton(text="◀️ Назад", callback_data=back_target))
    return b.as_markup()


def kb_payment(pay_link: str, back_target: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="💳 Оплатить", url=pay_link))
    b.row(InlineKeyboardButton(text="✅ Я оплатил(а)", callback_data="pay:confirm"))
    b.row(InlineKeyboardButton(text="◀️ Назад", callback_data=back_target))
    return b.as_markup()


def kb_contact_request() -> ReplyKeyboardMarkup:
    """Обычная (не инлайн) клавиатура с кнопкой запроса контакта — специальная функция Telegram."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📱 Отправить номер телефона", request_contact=True)],
            [KeyboardButton(text="◀️ Назад")],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def kb_consent(back_target: str = "consent:back") -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="✅ Согласен(на) и продолжить", callback_data="consent:accept"))
    b.row(InlineKeyboardButton(text="◀️ Назад", callback_data=back_target))
    return b.as_markup()


def kb_cancel_list(orders_with_labels: list[tuple[str, str]]) -> InlineKeyboardMarkup:
    """orders_with_labels: список (order_id, короткая_подпись)."""
    b = InlineKeyboardBuilder()
    for order_id, label in orders_with_labels:
        b.button(text=label, callback_data=f"cancelask:{order_id}")
    b.adjust(1)
    return b.as_markup()


def kb_cancel_confirm(order_id: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="❌ Да, отменить запись", callback_data=f"cancelconfirm:{order_id}"))
    b.row(InlineKeyboardButton(text="Нет, оставить как есть", callback_data="cancel:dismiss"))
    return b.as_markup()


def kb_equipment(equipment: list[tuple[str, str, int]], selected: set[str], back_target: str = "back:bp_location") -> InlineKeyboardMarkup:
    """equipment: список (key, label, price). selected: множество выбранных ключей (переключатели)."""
    b = InlineKeyboardBuilder()
    for key, label, price in equipment:
        mark = "✅" if key in selected else "⬜"
        b.button(text=f"{mark} {label} (+{price} ₽)", callback_data=f"equip:{key}")
    b.adjust(1)
    b.row(InlineKeyboardButton(text="Продолжить ➡️", callback_data="equip:done"))
    b.row(InlineKeyboardButton(text="◀️ Назад", callback_data=back_target))
    return b.as_markup()


def kb_bp_times(times: list[str], prices: dict[str, int], prefix: str, back_target: str) -> InlineKeyboardMarkup:
    """Как kb_times, но с ценой прямо на кнопке (цена может отличаться по времени суток)."""
    b = InlineKeyboardBuilder()
    for t in times:
        price = prices.get(t)
        label = f"{t} — {price} ₽" if price else t
        b.button(text=label, callback_data=f"{prefix}:{t}")
    b.adjust(2)
    b.row(InlineKeyboardButton(text="◀️ Назад", callback_data=back_target))
    return b.as_markup()