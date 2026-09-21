import logging
import datetime as dt

from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, ReplyKeyboardRemove

import keyboards as kb
from states import Flow
from data import (
    CATEGORY_LABELS,
    LOCATIONS,
    SPORT_LABELS,
    CONSENT_TEXT,
    normalize_phone,
    build_summary_text,
    build_final_info_text,
    build_offer_schedule_text,
    build_personal_schedule_text,
    build_order_short_label,
    build_order_detail_text,
    hours_until_order,
    CANCEL_MIN_HOURS,
    generate_payment_link,
    new_order_id,
    get_group_offers,
    get_personal_packages,
    get_personal_schedule,
    get_package_by_key,
    get_default_schedule,
    get_available_dates,
    format_date_label,
    get_time_slots_for_window,
    get_rental_time_slots_for_date,
    get_bp_locations,
    get_equipment_list,
    get_hour_slots,
    get_court_price,
)
from db import (
    get_or_create_client,
    create_order,
    mark_order_paid,
    get_booked_times,
    update_client_contact,
    get_client_by_tg_id,
    get_upcoming_orders,
    get_order_by_order_id,
    cancel_order,
)

router = Router()
log = logging.getLogger(__name__)

WELCOME_TEXT = (
    "👋 Добро пожаловать в спортивный клуб <b>TennisCapital</b>!\n\n"
    "Мы проводим занятия и сдаём корты в аренду сразу по трём направлениям.\n\n"
    "Выберите, что вас интересует:"
)


# ---------------------------------------------------------------------------
# /start
# ---------------------------------------------------------------------------
@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()

    user = message.from_user
    full_name = " ".join(filter(None, [user.first_name, user.last_name])) if user else None
    client = await get_or_create_client(
        tg_user_id=user.id,
        tg_username=user.username,
        full_name=full_name,
    )
    # Сохраняем внутренний id клиента (не telegram id!) в состоянии,
    # чтобы потом привязать к нему заявку в create_order().
    await state.update_data(client_id=client.id)

    await state.set_state(Flow.sport)
    await message.answer(WELCOME_TEXT, reply_markup=kb.kb_sport())


# ---------------------------------------------------------------------------
# Шаг 0: выбор вида спорта (теннис / бадминтон / пиклбол)
# ---------------------------------------------------------------------------
@router.callback_query(Flow.sport, F.data.startswith("sport:"))
async def on_sport(call: CallbackQuery, state: FSMContext):
    sport = call.data.split(":", 1)[1]
    await state.update_data(sport=sport)

    if sport == "tennis":
        await state.set_state(Flow.category)
        await call.message.edit_text(
            f"{SPORT_LABELS['tennis']}\n\nВыберите, что вас интересует:",
            reply_markup=kb.kb_category(back_target="back:sport"),
        )
    else:
        locations = get_bp_locations(sport)
        await state.set_state(Flow.bp_location)
        await call.message.edit_text(
            f"{SPORT_LABELS[sport]}\n\nВыберите удобную локацию:",
            reply_markup=kb.kb_locations(locations=locations, prefix="bploc", back_target="back:sport"),
        )
    await call.answer()


@router.callback_query(F.data == "back:sport")
async def back_to_sport(call: CallbackQuery, state: FSMContext):
    await state.set_state(Flow.sport)
    await call.message.edit_text(WELCOME_TEXT, reply_markup=kb.kb_sport())
    await call.answer()


# ---------------------------------------------------------------------------
# Шаг 1 (теннис): категория (детская / взрослая / аренда)
# ---------------------------------------------------------------------------
@router.callback_query(Flow.category, F.data.startswith("cat:"))
async def on_category(call: CallbackQuery, state: FSMContext):
    category = call.data.split(":", 1)[1]
    await state.update_data(category=category)

    if category == "rent":
        await state.set_state(Flow.rental_location)
        await call.message.edit_text(
            "🏟 <b>Аренда корта</b>\n\nВыберите удобную локацию:",
            reply_markup=kb.kb_locations(prefix="rloc", back_target="back:category"),
        )
    else:
        await state.set_state(Flow.lesson_type)
        label = CATEGORY_LABELS[category]
        await call.message.edit_text(
            f"{label}\n\nВыберите формат занятий:",
            reply_markup=kb.kb_lesson_type(),
        )
    await call.answer()


@router.callback_query(F.data == "back:category")
async def back_to_category(call: CallbackQuery, state: FSMContext):
    await state.set_state(Flow.category)
    await call.message.edit_text(
        f"{SPORT_LABELS['tennis']}\n\nВыберите, что вас интересует:",
        reply_markup=kb.kb_category(back_target="back:sport"),
    )
    await call.answer()


# ---------------------------------------------------------------------------
# Шаг 2 (школы): групповые / персональные
# ---------------------------------------------------------------------------
@router.callback_query(Flow.lesson_type, F.data.startswith("ltype:"))
async def on_lesson_type(call: CallbackQuery, state: FSMContext):
    lesson_type = call.data.split(":", 1)[1]
    await state.update_data(lesson_type=lesson_type)
    await state.set_state(Flow.subtype)

    if lesson_type == "group":
        await call.message.edit_text(
            "Выберите вид групповых занятий:",
            reply_markup=kb.kb_group_subtype(),
        )
    else:
        await call.message.edit_text(
            "Выберите формат персональных занятий:",
            reply_markup=kb.kb_personal_subtype(),
        )
    await call.answer()


@router.callback_query(F.data == "back:lesson_type")
async def back_to_lesson_type(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    category = data.get("category")
    await state.set_state(Flow.lesson_type)
    label = CATEGORY_LABELS.get(category, "")
    await call.message.edit_text(
        f"{label}\n\nВыберите формат занятий:",
        reply_markup=kb.kb_lesson_type(),
    )
    await call.answer()


# ---------------------------------------------------------------------------
# Шаг 3 (школы): подтип (спортивные/любительские/офп или индив./сплит/семейные)
# ---------------------------------------------------------------------------
@router.callback_query(Flow.subtype, F.data.startswith("group:"))
async def on_group_subtype(call: CallbackQuery, state: FSMContext):
    subtype = call.data.split(":", 1)[1]
    await state.update_data(subtype=subtype)
    await state.set_state(Flow.level)
    await call.message.edit_text(
        "Подскажите ваш уровень подготовки — так мы сразу подберём подходящую группу:",
        reply_markup=kb.kb_level(back_target="back:subtype"),
    )
    await call.answer()


@router.callback_query(Flow.subtype, F.data.startswith("personal:"))
async def on_personal_subtype(call: CallbackQuery, state: FSMContext):
    subtype = call.data.split(":", 1)[1]
    await state.update_data(subtype=subtype)
    await state.set_state(Flow.level)
    await call.message.edit_text(
        "Подскажите ваш уровень подготовки — тренер адаптирует программу под вас:",
        reply_markup=kb.kb_level(back_target="back:subtype"),
    )
    await call.answer()


@router.callback_query(F.data == "back:subtype")
async def back_to_subtype(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    lesson_type = data.get("lesson_type")
    await state.set_state(Flow.subtype)
    if lesson_type == "group":
        await call.message.edit_text(
            "Выберите вид групповых занятий:",
            reply_markup=kb.kb_group_subtype(),
        )
    else:
        await call.message.edit_text(
            "Выберите формат персональных занятий:",
            reply_markup=kb.kb_personal_subtype(),
        )
    await call.answer()


# ---------------------------------------------------------------------------
# Шаг 4 (школы): уровень подготовки -> выбор локации
# ---------------------------------------------------------------------------
@router.callback_query(Flow.level, F.data.startswith("level:"))
async def on_level(call: CallbackQuery, state: FSMContext):
    level = call.data.split(":", 1)[1]
    await state.update_data(level=level)
    await state.set_state(Flow.location)
    await call.message.edit_text(
        "Отлично! Теперь выберите удобную локацию:",
        reply_markup=kb.kb_locations(prefix="loc", back_target="back:level"),
    )
    await call.answer()


@router.callback_query(F.data == "back:level")
async def back_to_level(call: CallbackQuery, state: FSMContext):
    await state.set_state(Flow.level)
    await call.message.edit_text(
        "Подскажите ваш уровень подготовки:",
        reply_markup=kb.kb_level(back_target="back:subtype"),
    )
    await call.answer()


# ---------------------------------------------------------------------------
# Шаг 5 (школы): локация -> формат группы (если их несколько) / прайс-лист
# персональных -> дата/время
# ---------------------------------------------------------------------------
@router.callback_query(Flow.location, F.data.startswith("loc:"))
async def on_location(call: CallbackQuery, state: FSMContext):
    idx = int(call.data.split(":", 1)[1])
    location = LOCATIONS[idx]
    await state.update_data(location=location)
    data = await state.get_data()

    if data["lesson_type"] == "personal":
        packages = get_personal_packages(location, data["subtype"])
        if packages:
            sched = get_personal_schedule(location)
            await store_schedule(state, sched)
            await show_package_step(
                call, state, packages,
                info_text=build_personal_schedule_text(sched),
                back_target="back:location",
            )
        else:
            await store_schedule(state, get_default_schedule("personal"))
            await start_contact_step(call, state)
    else:  # group
        offers = get_group_offers(location, data["category"])
        if not offers:
            await store_schedule(state, get_default_schedule("group"))
            await start_contact_step(call, state)
        elif len(offers) == 1:
            await select_group_offer(call, state, offers[0])
        else:
            await state.set_state(Flow.offer_format)
            await call.message.edit_text(
                "В этой локации доступно несколько форматов групповых занятий. "
                "Выберите нужный:",
                reply_markup=kb.kb_offer_formats(offers, back_target="back:location"),
            )
    await call.answer()


@router.callback_query(F.data == "back:location")
async def back_to_location(call: CallbackQuery, state: FSMContext):
    await state.set_state(Flow.location)
    await call.message.edit_text(
        "Выберите удобную локацию:",
        reply_markup=kb.kb_locations(prefix="loc", back_target="back:level"),
    )
    await call.answer()


async def store_schedule(state: FSMContext, sched: dict):
    """Сохраняет действующее расписание (будни/выходные) в FSM для шагов даты/времени."""
    await state.update_data(
        schedule_weekday_start=sched["weekday"][0],
        schedule_weekday_end=sched["weekday"][1],
        schedule_weekend_start=sched["weekend"][0],
        schedule_weekend_end=sched["weekend"][1],
    )


# ---------------------------------------------------------------------------
# Шаг 5.5 (только если в локации несколько форматов групп): выбор формата
# ---------------------------------------------------------------------------
async def select_group_offer(call: CallbackQuery, state: FSMContext, offer: dict):
    data = await state.get_data()
    category = data["category"]
    sched = offer["schedule"].get(category) or next(iter(offer["schedule"].values()))
    await state.update_data(group_offer_key=offer["key"])
    await store_schedule(state, sched)
    info_text = build_offer_schedule_text(offer, category)
    await show_package_step(call, state, offer["packages"], info_text=info_text, back_target="back:location")


@router.callback_query(Flow.offer_format, F.data.startswith("offerfmt:"))
async def on_offer_format(call: CallbackQuery, state: FSMContext):
    key = call.data.split(":", 1)[1]
    data = await state.get_data()
    offers = get_group_offers(data["location"], data["category"])
    offer = next((o for o in offers if o["key"] == key), None)
    if offer:
        await select_group_offer(call, state, offer)
    await call.answer()


@router.callback_query(F.data == "back:offer_format")
async def back_to_offer_format(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    offers = get_group_offers(data["location"], data["category"])
    await state.set_state(Flow.offer_format)
    await call.message.edit_text(
        "В этой локации доступно несколько форматов групповых занятий. Выберите нужный:",
        reply_markup=kb.kb_offer_formats(offers, back_target="back:location"),
    )
    await call.answer()


# ---------------------------------------------------------------------------
# Шаг 6 (школы): выбор тарифа
# ---------------------------------------------------------------------------
async def show_package_step(call: CallbackQuery, state: FSMContext, packages, info_text: str, back_target: str):
    await state.set_state(Flow.package)
    await call.message.edit_text(
        info_text,
        reply_markup=kb.kb_packages(packages, prefix="pkg", back_target=back_target),
    )


@router.callback_query(Flow.package, F.data.startswith("pkg:"))
async def on_package(call: CallbackQuery, state: FSMContext):
    key = call.data.split(":", 1)[1]
    data = await state.get_data()
    packages = await _current_packages(data)
    pkg = get_package_by_key(packages, key) if packages else None
    if pkg:
        pkg_key, pkg_label, pkg_price = pkg
        await state.update_data(package_key=pkg_key, package_label=pkg_label, package_price=pkg_price)

    await start_contact_step(call, state)
    await call.answer()


async def _current_packages(data: dict):
    """Восстанавливает список пакетов текущего шага (персональные или групповой оффер)."""
    if data.get("lesson_type") == "personal":
        return get_personal_packages(data["location"], data["subtype"])
    offers = get_group_offers(data["location"], data["category"])
    offer = next((o for o in offers if o["key"] == data.get("group_offer_key")), None)
    return offer["packages"] if offer else None


@router.callback_query(F.data == "back:package")
async def back_to_package(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    if data.get("lesson_type") == "personal":
        packages = get_personal_packages(data["location"], data["subtype"])
        sched = get_personal_schedule(data["location"])
        if packages:
            await show_package_step(
                call, state, packages,
                info_text=build_personal_schedule_text(sched),
                back_target="back:location",
            )
    else:
        offers = get_group_offers(data["location"], data["category"])
        offer = next((o for o in offers if o["key"] == data.get("group_offer_key")), None)
        if offer:
            back_target = "back:offer_format" if len(offers) > 1 else "back:location"
            info_text = build_offer_schedule_text(offer, data["category"])
            await show_package_step(call, state, offer["packages"], info_text=info_text, back_target=back_target)
    await call.answer()


# ---------------------------------------------------------------------------
# Шаг 7 (школы): выбор даты (ближайшие 2 недели)
# ---------------------------------------------------------------------------
async def show_date_step(call: CallbackQuery, state: FSMContext, back_target: str):
    await state.set_state(Flow.date)
    dates = get_available_dates()
    labels = [format_date_label(d) for d in dates]
    await call.message.edit_text(
        "Выберите дату записи (ближайшие 2 недели):",
        reply_markup=kb.kb_dates(dates, labels, prefix="date", back_target=back_target),
    )


@router.callback_query(Flow.date, F.data.startswith("date:"))
async def on_date(call: CallbackQuery, state: FSMContext):
    idx = int(call.data.split(":", 1)[1])
    dates = get_available_dates()
    selected_date = dates[idx]
    await state.update_data(booking_date=selected_date.isoformat())
    await state.set_state(Flow.time)
    await show_time_step(call, state, selected_date)
    await call.answer()


@router.callback_query(F.data == "back:date")
async def back_to_date(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    if data.get("lesson_type") == "personal":
        packages = get_personal_packages(data["location"], data["subtype"])
        back_target = "back:package" if packages else "back:location"
    else:
        offers = get_group_offers(data["location"], data["category"])
        offer = next((o for o in offers if o["key"] == data.get("group_offer_key")), None)
        back_target = "back:package" if offer else "back:location"
    await show_date_step(call, state, back_target=back_target)
    await call.answer()


# ---------------------------------------------------------------------------
# Шаг 8 (школы): выбор времени (занятые слоты не показываются)
# ---------------------------------------------------------------------------
async def show_time_step(call: CallbackQuery, state: FSMContext, selected_date):
    data = await state.get_data()
    booked = await get_booked_times(data["location"], selected_date, sport=data.get("sport", "tennis"))
    all_slots = get_time_slots_for_window(
        data["schedule_weekday_start"], data["schedule_weekday_end"],
        data["schedule_weekend_start"], data["schedule_weekend_end"],
        selected_date,
    )
    free_slots = [t for t in all_slots if t not in booked]

    if not free_slots:
        await call.message.edit_text(
            f"На {format_date_label(selected_date)} свободного времени не осталось. "
            f"Пожалуйста, выберите другую дату.",
            reply_markup=kb.kb_times([], prefix="time", back_target="back:date"),
        )
        return

    await call.message.edit_text(
        f"Выберите время на {format_date_label(selected_date)}:",
        reply_markup=kb.kb_times(free_slots, prefix="time", back_target="back:date"),
    )


@router.callback_query(Flow.time, F.data.startswith("time:"))
async def on_time(call: CallbackQuery, state: FSMContext):
    time_str = call.data.split(":", 1)[1]
    await state.update_data(booking_time=time_str)
    await state.set_state(Flow.payment)
    await send_summary_and_payment(call, state, back_target="back:date")
    await call.answer()


# ---------------------------------------------------------------------------
# Контакт, имя и согласие с документами.
# Вставляется между выбором тарифа/локации и выбором даты — как для школ,
# так и для аренды корта. Номер телефона запрашивается через нативную
# функцию Telegram (кнопка "Отправить контакт"), но разрешён и ручной ввод.
# ---------------------------------------------------------------------------
async def start_contact_step(call: CallbackQuery, state: FSMContext):
    await state.set_state(Flow.contact)
    await call.message.edit_text(
        "Отлично! Остался последний шаг перед выбором даты — контактные данные."
    )
    await call.message.answer(
        "Пожалуйста, поделитесь номером телефона (нажмите кнопку ниже) "
        "или введите его вручную, например: +7 999 123-45-67",
        reply_markup=kb.kb_contact_request(),
    )


async def _resend_contact_prompt(message: Message, state: FSMContext):
    """Повторный показ шага телефона — используется при возврате назад с шага имени."""
    await state.set_state(Flow.contact)
    await message.answer(
        "Хорошо, введите номер телефона ещё раз, или поделитесь контактом:",
        reply_markup=kb.kb_contact_request(),
    )


async def _back_from_contact(message: Message, state: FSMContext):
    """
    Возврат с шага контакта на предыдущий (инлайн) экран — тариф/локация
    для школ, длительность для аренды тенниса, или инвентарь для
    бадминтона/пиклбола. Рендерится новым сообщением, так как обычная
    (не инлайн) клавиатура уже была показана.
    """
    await message.answer("Хорошо, возвращаемся назад.", reply_markup=ReplyKeyboardRemove())
    data = await state.get_data()
    sport = data.get("sport", "tennis")

    if sport in ("badminton", "pickleball"):
        equipment_list = get_equipment_list(sport)
        selected = set(data.get("equipment_keys", []))
        await state.set_state(Flow.equipment)
        await message.answer(
            EQUIPMENT_PROMPT_TEXT,
            reply_markup=kb.kb_equipment(equipment_list, selected, back_target="back:bp_location"),
        )
        return

    if data.get("category") == "rent":
        await state.set_state(Flow.rental_duration)
        await message.answer(
            "На какое время хотите арендовать корт?",
            reply_markup=kb.kb_rental_duration(),
        )
        return

    packages = await _current_packages(data)
    if packages:
        if data.get("lesson_type") == "personal":
            sched = get_personal_schedule(data["location"])
            info_text = build_personal_schedule_text(sched)
            back_target = "back:location"
        else:
            offers = get_group_offers(data["location"], data["category"])
            offer = next((o for o in offers if o["key"] == data.get("group_offer_key")), None)
            info_text = build_offer_schedule_text(offer, data["category"])
            back_target = "back:offer_format" if len(offers) > 1 else "back:location"
        await state.set_state(Flow.package)
        await message.answer(info_text, reply_markup=kb.kb_packages(packages, prefix="pkg", back_target=back_target))
    else:
        await state.set_state(Flow.location)
        await message.answer(
            "Выберите удобную локацию:",
            reply_markup=kb.kb_locations(prefix="loc", back_target="back:level"),
        )


@router.message(Flow.contact, F.text == "◀️ Назад")
async def on_contact_back(message: Message, state: FSMContext):
    await _back_from_contact(message, state)


@router.message(Flow.contact, F.contact)
async def on_contact_shared(message: Message, state: FSMContext):
    phone = normalize_phone(message.contact.phone_number)
    if not phone:
        await message.answer(
            "Не удалось распознать номер телефона. Попробуйте ввести его вручную, "
            "например: +7 999 123-45-67"
        )
        return
    await state.update_data(client_phone=phone)
    await _proceed_to_name(message, state)


@router.message(Flow.contact, F.text)
async def on_contact_text(message: Message, state: FSMContext):
    phone = normalize_phone(message.text.strip())
    if not phone:
        await message.answer(
            "Похоже, это не похоже на номер телефона. Введите его в формате "
            "+7 999 123-45-67 или 8 999 123-45-67, либо нажмите кнопку "
            "«Отправить номер телефона» ниже."
        )
        return
    await state.update_data(client_phone=phone)
    await _proceed_to_name(message, state)


async def _proceed_to_name(message: Message, state: FSMContext):
    await state.set_state(Flow.name)
    await message.answer(
        "Спасибо! Теперь, пожалуйста, напишите ваше имя (настоящее имя, не никнейм):",
        reply_markup=ReplyKeyboardRemove(),
    )


@router.message(Flow.name, F.text == "◀️ Назад")
async def on_name_back(message: Message, state: FSMContext):
    await _resend_contact_prompt(message, state)


@router.message(Flow.name, F.text)
async def on_name_text(message: Message, state: FSMContext):
    name = message.text.strip()
    if len(name) < 2:
        await message.answer("Пожалуйста, укажите настоящее имя (минимум 2 символа).")
        return
    await state.update_data(client_name=name)
    await _show_consent_step(message, state)


async def _show_consent_step(message: Message, state: FSMContext):
    await state.set_state(Flow.consent)
    await message.answer(CONSENT_TEXT, reply_markup=kb.kb_consent(back_target="consent:back"))


@router.callback_query(Flow.consent, F.data == "consent:accept")
async def on_consent_accept(call: CallbackQuery, state: FSMContext):
    await state.update_data(
        consent_given=True,
        consent_at=dt.datetime.utcnow().isoformat(),
    )
    data = await state.get_data()

    # Сохраняем контакт в профиль клиента (Client) как последние известные данные.
    await update_client_contact(
        client_id=data["client_id"],
        phone=data.get("client_phone"),
        full_name=data.get("client_name"),
    )

    await call.message.edit_text("Спасибо! Продолжаем запись.")

    sport = data.get("sport", "tennis")
    if sport in ("badminton", "pickleball"):
        await show_bp_date_step(call, state, back_target="back:equipment")
    elif data.get("category") == "rent":
        await show_rental_date_step(call, state, back_target="back:rental_duration")
    else:
        packages = await _current_packages(data)
        back_target = "back:package" if packages else "back:location"
        await show_date_step(call, state, back_target=back_target)
    await call.answer()


@router.callback_query(Flow.consent, F.data == "consent:back")
async def on_consent_back(call: CallbackQuery, state: FSMContext):
    await state.set_state(Flow.name)
    await call.message.edit_text("Хорошо, укажите, пожалуйста, ваше имя ещё раз:")
    await call.answer()


# ---------------------------------------------------------------------------
# Ветка аренды корта: локация -> длительность -> дата -> время -> оплата
# ---------------------------------------------------------------------------
@router.callback_query(Flow.rental_location, F.data.startswith("rloc:"))
async def on_rental_location(call: CallbackQuery, state: FSMContext):
    idx = int(call.data.split(":", 1)[1])
    location = LOCATIONS[idx]
    await state.update_data(rental_location=location)
    await state.set_state(Flow.rental_duration)
    await call.message.edit_text(
        "На какое время хотите арендовать корт?",
        reply_markup=kb.kb_rental_duration(),
    )
    await call.answer()


@router.callback_query(F.data == "back:rental_location")
async def back_to_rental_location(call: CallbackQuery, state: FSMContext):
    await state.set_state(Flow.rental_location)
    await call.message.edit_text(
        "🏟 <b>Аренда корта</b>\n\nВыберите удобную локацию:",
        reply_markup=kb.kb_locations(prefix="rloc", back_target="back:category"),
    )
    await call.answer()


@router.callback_query(Flow.rental_duration, F.data.startswith("dur:"))
async def on_rental_duration(call: CallbackQuery, state: FSMContext):
    duration = call.data.split(":", 1)[1]
    await state.update_data(rental_duration=duration)
    await start_contact_step(call, state)
    await call.answer()


@router.callback_query(F.data == "back:rental_duration")
async def back_to_rental_duration(call: CallbackQuery, state: FSMContext):
    await state.set_state(Flow.rental_duration)
    await call.message.edit_text(
        "На какое время хотите арендовать корт?",
        reply_markup=kb.kb_rental_duration(),
    )
    await call.answer()


async def show_rental_date_step(call: CallbackQuery, state: FSMContext, back_target: str):
    data = await state.get_data()
    await state.set_state(Flow.rental_date)
    dates = get_available_dates()
    labels = [format_date_label(d) for d in dates]
    await call.message.edit_text(
        "Выберите дату аренды (ближайшие 2 недели):",
        reply_markup=kb.kb_dates(dates, labels, prefix="rdate", back_target=back_target),
    )


@router.callback_query(Flow.rental_date, F.data.startswith("rdate:"))
async def on_rental_date(call: CallbackQuery, state: FSMContext):
    idx = int(call.data.split(":", 1)[1])
    data = await state.get_data()
    dates = get_available_dates()
    selected_date = dates[idx]
    await state.update_data(booking_date=selected_date.isoformat())
    await state.set_state(Flow.rental_time)
    await show_rental_time_step(call, state, selected_date)
    await call.answer()


@router.callback_query(F.data == "back:rental_date")
async def back_to_rental_date(call: CallbackQuery, state: FSMContext):
    await show_rental_date_step(call, state, back_target="back:rental_duration")
    await call.answer()


async def show_rental_time_step(call: CallbackQuery, state: FSMContext, selected_date):
    data = await state.get_data()
    duration_minutes = int(data["rental_duration"])
    booked = await get_booked_times(data["rental_location"], selected_date, sport=data.get("sport", "tennis"))
    all_slots = get_rental_time_slots_for_date(duration_minutes, selected_date)
    free_slots = [t for t in all_slots if t not in booked]

    if not free_slots:
        await call.message.edit_text(
            f"На {format_date_label(selected_date)} свободных слотов такой длительности не осталось. "
            f"Пожалуйста, выберите другую дату.",
            reply_markup=kb.kb_times([], prefix="rtime", back_target="back:rental_date"),
        )
        return

    await call.message.edit_text(
        f"Выберите время на {format_date_label(selected_date)}:",
        reply_markup=kb.kb_times(free_slots, prefix="rtime", back_target="back:rental_date"),
    )


@router.callback_query(Flow.rental_time, F.data.startswith("rtime:"))
async def on_rental_time(call: CallbackQuery, state: FSMContext):
    time_str = call.data.split(":", 1)[1]
    await state.update_data(booking_time=time_str)
    await state.set_state(Flow.payment)
    await send_summary_and_payment(call, state, back_target="back:rental_date")
    await call.answer()


# ---------------------------------------------------------------------------
# Ветка бадминтона/пиклбола: локация -> инвентарь -> (контакт/имя/согласие,
# обработчики уже выше) -> дата -> время (цена своя для каждого часа) -> оплата
# ---------------------------------------------------------------------------
EQUIPMENT_PROMPT_TEXT = "Нужен ли инвентарь? Отметьте нужное и нажмите «Продолжить»:"


@router.callback_query(Flow.bp_location, F.data.startswith("bploc:"))
async def on_bp_location(call: CallbackQuery, state: FSMContext):
    idx = int(call.data.split(":", 1)[1])
    data = await state.get_data()
    locations = get_bp_locations(data["sport"])
    location = locations[idx]
    await state.update_data(bp_location=location, equipment_keys=[])

    equipment_list = get_equipment_list(data["sport"])
    await state.set_state(Flow.equipment)
    await call.message.edit_text(
        EQUIPMENT_PROMPT_TEXT,
        reply_markup=kb.kb_equipment(equipment_list, set(), back_target="back:bp_location"),
    )
    await call.answer()


@router.callback_query(F.data == "back:bp_location")
async def back_to_bp_location(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    sport = data["sport"]
    locations = get_bp_locations(sport)
    await state.set_state(Flow.bp_location)
    await call.message.edit_text(
        f"{SPORT_LABELS[sport]}\n\nВыберите удобную локацию:",
        reply_markup=kb.kb_locations(locations=locations, prefix="bploc", back_target="back:sport"),
    )
    await call.answer()


@router.callback_query(Flow.equipment, F.data.startswith("equip:"))
async def on_equipment_toggle(call: CallbackQuery, state: FSMContext):
    key = call.data.split(":", 1)[1]
    data = await state.get_data()
    equipment_list = get_equipment_list(data["sport"])

    if key == "done":
        await start_contact_step(call, state)
        await call.answer()
        return

    selected = set(data.get("equipment_keys", []))
    if key in selected:
        selected.discard(key)
    else:
        selected.add(key)
    await state.update_data(equipment_keys=list(selected))
    await call.message.edit_text(
        EQUIPMENT_PROMPT_TEXT,
        reply_markup=kb.kb_equipment(equipment_list, selected, back_target="back:bp_location"),
    )
    await call.answer()


@router.callback_query(F.data == "back:equipment")
async def back_to_equipment(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    equipment_list = get_equipment_list(data["sport"])
    selected = set(data.get("equipment_keys", []))
    await state.set_state(Flow.equipment)
    await call.message.edit_text(
        EQUIPMENT_PROMPT_TEXT,
        reply_markup=kb.kb_equipment(equipment_list, selected, back_target="back:bp_location"),
    )
    await call.answer()


async def show_bp_date_step(call: CallbackQuery, state: FSMContext, back_target: str):
    await state.set_state(Flow.bp_date)
    dates = get_available_dates()
    labels = [format_date_label(d) for d in dates]
    await call.message.edit_text(
        "Выберите дату аренды (ближайшие 2 недели):",
        reply_markup=kb.kb_dates(dates, labels, prefix="bpdate", back_target=back_target),
    )


@router.callback_query(Flow.bp_date, F.data.startswith("bpdate:"))
async def on_bp_date(call: CallbackQuery, state: FSMContext):
    idx = int(call.data.split(":", 1)[1])
    dates = get_available_dates()
    selected_date = dates[idx]
    await state.update_data(booking_date=selected_date.isoformat())
    await state.set_state(Flow.bp_time)
    await show_bp_time_step(call, state, selected_date)
    await call.answer()


@router.callback_query(F.data == "back:bp_date")
async def back_to_bp_date(call: CallbackQuery, state: FSMContext):
    await show_bp_date_step(call, state, back_target="back:equipment")
    await call.answer()


async def show_bp_time_step(call: CallbackQuery, state: FSMContext, selected_date):
    data = await state.get_data()
    sport = data["sport"]
    location = data["bp_location"]
    is_weekend = selected_date.weekday() >= 5

    booked = await get_booked_times(location, selected_date, sport=sport)
    all_slots = get_hour_slots()
    free_slots = [t for t in all_slots if t not in booked]

    if not free_slots:
        await call.message.edit_text(
            f"На {format_date_label(selected_date)} свободных часов не осталось. "
            f"Пожалуйста, выберите другую дату.",
            reply_markup=kb.kb_times([], prefix="bptime", back_target="back:bp_date"),
        )
        return

    prices = {t: get_court_price(sport, is_weekend, t) for t in free_slots}
    await call.message.edit_text(
        f"Выберите время на {format_date_label(selected_date)}:",
        reply_markup=kb.kb_bp_times(free_slots, prices, prefix="bptime", back_target="back:bp_date"),
    )


@router.callback_query(Flow.bp_time, F.data.startswith("bptime:"))
async def on_bp_time(call: CallbackQuery, state: FSMContext):
    time_str = call.data.split(":", 1)[1]
    data = await state.get_data()
    sport = data["sport"]
    selected_date = dt.date.fromisoformat(data["booking_date"])
    is_weekend = selected_date.weekday() >= 5

    court_price = get_court_price(sport, is_weekend, time_str)
    equipment_keys = data.get("equipment_keys", [])
    equipment_list = get_equipment_list(sport)
    chosen_equipment = [(label, price) for key, label, price in equipment_list if key in equipment_keys]
    equipment_total = sum(price for _, price in chosen_equipment)
    total_price = court_price + equipment_total

    label_parts = [f"Аренда корта (1 час) — {court_price} ₽"] + [
        f"{label} — {price} ₽" for label, price in chosen_equipment
    ]
    package_label = "; ".join(label_parts)

    await state.update_data(
        booking_time=time_str,
        package_key="court_rental",
        package_label=package_label,
        package_price=total_price,
    )
    await state.set_state(Flow.payment)
    await send_summary_and_payment(call, state, back_target="back:bp_date")
    await call.answer()


# ---------------------------------------------------------------------------
# Общий шаг: показать summary и ссылку на оплату
# ---------------------------------------------------------------------------
async def send_summary_and_payment(call: CallbackQuery, state: FSMContext, back_target: str):
    data = await state.get_data()
    order_id = new_order_id()
    await state.update_data(order_id=order_id)
    data["order_id"] = order_id

    # Сохраняем заявку в БД в статусе "pending" уже на этом шаге — так у нас
    # остаётся след даже если клиент так и не оплатит (можно будет догнать
    # напоминанием или посмотреть в отчёте, где отваливаются клиенты). Это же
    # сразу "бронирует" выбранный слот времени — он перестанет предлагаться
    # другим клиентам, даже если оплата ещё не подтверждена.
    await create_order(client_id=data["client_id"], order_id=order_id, data=data)

    summary = build_summary_text(data)
    pay_link = generate_payment_link(order_id)

    text = (
        f"{summary}\n\n"
        f"💳 Для завершения записи оплатите по ссылке ниже, "
        f"а после оплаты нажмите «Я оплатил(а)»."
    )
    await call.message.edit_text(text, reply_markup=kb.kb_payment(pay_link, back_target))


# ---------------------------------------------------------------------------
# Подтверждение оплаты
# ---------------------------------------------------------------------------
@router.callback_query(Flow.payment, F.data == "pay:confirm")
async def on_payment_confirm(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()

    # ЗАГЛУШКА: реальная проверка оплаты должна идти через webhook платёжной
    # системы, а не по нажатию кнопки пользователем. Здесь для демонстрации
    # мы считаем оплату подтверждённой сразу после нажатия.
    await mark_order_paid(data["order_id"])

    final_text = build_final_info_text(data)
    await call.message.edit_text(final_text)
    await call.answer("Оплата подтверждена ✅")

    log.info("Новая запись оформлена: %s", data)
    # Здесь можно отправить уведомление администраторам клуба, например:
    # for admin_id in ADMIN_IDS:
    #     await call.bot.send_message(admin_id, f"Новая запись:\n{build_summary_text(data)}")

    await state.clear()


# ---------------------------------------------------------------------------
# Отмена записи: /cancel
# ---------------------------------------------------------------------------
@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    client = await get_client_by_tg_id(message.from_user.id)
    if not client:
        await message.answer("У вас пока нет ни одной записи.")
        return

    orders = await get_upcoming_orders(client.id)
    if not orders:
        await message.answer("У вас нет предстоящих записей, которые можно отменить.")
        return

    orders_with_labels = [(o.order_id, build_order_short_label(o)) for o in orders]
    await message.answer(
        "Выберите запись, которую хотите отменить:",
        reply_markup=kb.kb_cancel_list(orders_with_labels),
    )


@router.callback_query(F.data.startswith("cancelask:"))
async def on_cancel_ask(call: CallbackQuery, state: FSMContext):
    order_id = call.data.split(":", 1)[1]
    order = await get_order_by_order_id(order_id)
    if not order:
        await call.answer("Запись не найдена — возможно, уже отменена.", show_alert=True)
        return

    hours_left = hours_until_order(order)
    if hours_left is None or hours_left < CANCEL_MIN_HOURS:
        await call.message.edit_text(
            f"⚠️ Эту запись уже нельзя отменить самостоятельно — до начала осталось "
            f"меньше {CANCEL_MIN_HOURS} часов (или дата/время не заданы).\n\n"
            f"{build_order_detail_text(order)}\n\n"
            f"Если это форс-мажор, свяжитесь с администратором: "
            f"@tenniscapital_admin (заглушка)."
        )
        await call.answer()
        return

    await call.message.edit_text(
        f"Вы уверены, что хотите отменить эту запись?\n\n{build_order_detail_text(order)}",
        reply_markup=kb.kb_cancel_confirm(order_id),
    )
    await call.answer()


@router.callback_query(F.data.startswith("cancelconfirm:"))
async def on_cancel_confirm(call: CallbackQuery, state: FSMContext):
    order_id = call.data.split(":", 1)[1]
    order = await get_order_by_order_id(order_id)

    # Перепроверяем правило 12 часов ещё раз прямо перед отменой — на случай,
    # если пользователь долго держал открытым экран подтверждения.
    hours_left = hours_until_order(order) if order else None
    if order is None or hours_left is None or hours_left < CANCEL_MIN_HOURS:
        await call.message.edit_text(
            f"⚠️ К сожалению, отменить уже нельзя — до начала осталось меньше "
            f"{CANCEL_MIN_HOURS} часов. Свяжитесь с администратором: "
            f"@tenniscapital_admin (заглушка)."
        )
        await call.answer()
        return

    await cancel_order(order_id)
    await call.message.edit_text(
        "✅ Запись отменена. Если захотите записаться снова — просто наберите /start."
    )
    await call.answer("Запись отменена")


@router.callback_query(F.data == "cancel:dismiss")
async def on_cancel_dismiss(call: CallbackQuery, state: FSMContext):
    await call.message.edit_text("Хорошо, запись остаётся в силе. 👍")
    await call.answer()


# ---------------------------------------------------------------------------
# Фолбэк на случай устаревших/битых callback'ов
# ---------------------------------------------------------------------------
@router.callback_query()
async def fallback_callback(call: CallbackQuery, state: FSMContext):
    await call.answer(
        "Похоже, эта кнопка устарела. Наберите /start, чтобы начать заново.",
        show_alert=True,
    )