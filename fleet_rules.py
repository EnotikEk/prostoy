"""Правила учёта документов плавсостава и АСО: сроки, ограничения дипломов, проверка назначений."""
import calendar
import re
from datetime import date, datetime

# Должности по умолчанию (ТЗ, п.2). Список редактируется в справочнике.
DEFAULT_POSITIONS = [
    'капитан',
    'старший помощник капитана',
    'помощник капитана',
    'судоводитель маломерного судна, используемого в коммерческих целях',
    'механик',
    'первый помощник механика',
    'помощник механика',
    'капитан-механик',
    'старший помощник капитана - первый помощник механика',
    'помощник капитана - помощник механика',
    'командир земснаряда',
    'первый помощник командира земснаряда',
    'помощник командира земснаряда',
    'командир земснаряда - механик',
    'первый помощник командира земснаряда - первый помощник механика',
    'помощник командира земснаряда - помощник механика',
    'электромеханик',
    'первый помощник электромеханика',
    'помощник электромеханика',
    'шкипер',
    'рулевой',
    'матрос',
    'моторист',
    'лебёдчик',
    'электрик судовой',
    'повар судовой',
    'моторист-рулевой',
    'моторист-матрос',
    'лебёдчик-моторист',
]

# Филиалы — фиксированный список для всех выпадающих списков
BRANCHES = [
    'БУС',
    'НРВПиС',
    'НЛРВПиС',
    'ФБУ "Администрация "Волго-Балт"',
    'ШРГСиС',
    'СРГСиС',
    'ВРГСиС',
    'ГРВПиС',
    'ЧРВПиС',
]


def normalize_branch(value):
    """Значение из формы или Excel -> филиал из списка (без учёта регистра и пробелов) или None."""
    key = re.sub(r'\s+', ' ', str(value or '')).strip().lower()
    return next((b for b in BRANCHES if b.lower() == key), None)


def branch_order(value):
    """Порядок филиала в списке; суда без филиала — в конце."""
    return BRANCHES.index(value) if value in BRANCHES else len(BRANCHES)


DICTIONARY_KINDS = {
    'position': 'Должности',
    'training': 'Наименования доп. подготовки',
}

EDUCATION_LEVELS = ['ДПО', 'СПО', 'ПП', 'ВПО']

YES_NO = ['Да', 'Нет']

# Ограничения к рабочим дипломам (ТЗ, п.3 Г)
RESTRICTIONS = {
    'radar': 'Недействительно для работы судоводителем на судах с радиолокационными станциями',
    'ecdis': 'Недействительно для работы судоводителем на судах с электронными картами',
    'dredger700': 'Недействительно для работы членом экипажа земснаряда производительностью более 700 м³/ч',
    'passenger': 'Недействительно для работы на пассажирских судах',
    'tanker': 'Недействительно для работы на наливных судах, осуществляющих перевозки опасных грузов',
    'power330': 'Недействительно для работы на судах с мощностью главных двигателей более 330 кВт',
}

# ==================== СРОКИ ====================

# Уровни подсветки по возрастанию срочности
EXPIRY_LEVELS = ['year', 'half', 'month', 'expired']
EXPIRY_TITLES = {
    'year': 'До окончания срока меньше года',
    'half': 'До окончания срока меньше полугода',
    'month': 'До окончания срока меньше месяца',
    'expired': 'Срок наступил',
}


def add_months(d, months):
    month = d.month - 1 + months
    year = d.year + month // 12
    month = month % 12 + 1
    return date(year, month, min(d.day, calendar.monthrange(year, month)[1]))


def parse_date(value):
    """Дата из формы (гггг-мм-дд) или из текста характеристик (дд.мм.гггг). Иначе None."""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value or '').strip()
    for fmt in ('%Y-%m-%d', '%d.%m.%Y'):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            pass
    return None


def expiry_level(value, today=None):
    """Подсветка срока: год, полгода, месяц до даты — 'year'/'half'/'month', дата наступила — 'expired'."""
    d = parse_date(value)
    if d is None:
        return None
    today = today or date.today()
    if d <= today:
        return 'expired'
    if d <= add_months(today, 1):
        return 'month'
    if d <= add_months(today, 6):
        return 'half'
    if d <= add_months(today, 12):
        return 'year'
    return None


def worst_level(levels):
    ranked = [EXPIRY_LEVELS.index(lv) for lv in levels if lv]
    return EXPIRY_LEVELS[max(ranked)] if ranked else None


# ==================== СУДНО ====================

SHIP_CLASSES = ['РКО', 'М.С.', 'ГИМС']


def ship_class(ship):
    """Класс судна для списка: ГИМС и М.С. указываются в графе СУБ, остальные — суда РКО."""
    sub = re.sub(r'[\s.]', '', (ship.sub or '')).upper()
    if sub == 'ГИМС':
        return 'ГИМС'
    if sub == 'МС':
        return 'М.С.'
    if ship.rko_class or ship.sub:
        return 'РКО'
    return ''


def ship_doc_level(ship):
    """Наихудший срок по документам судна: ежегодное РКО и СУБ."""
    return worst_level([expiry_level(ship.annual_rko), expiry_level(ship.sub)])


def _number(value):
    match = re.search(r'\d+(?:[.,]\d+)?', str(value or ''))
    return float(match.group().replace(',', '.')) if match else None


def _type_has(ship, *words):
    ship_type = (ship.ship_type or '').lower()
    return any(w in ship_type for w in words)


# Должности судоводителей: капитаны и их помощники, командиры земснарядов и их помощники,
# судоводитель маломерного судна (в т.ч. совмещённые должности)
NAVIGATOR_WORDS = ('капитан', 'командир', 'судоводитель')


def is_navigator(position_name):
    name = (position_name or '').lower()
    return any(w in name for w in NAVIGATOR_WORDS)


def restriction_applies(code, ship, position_name):
    """Нарушает ли работа на этом судне в этой должности ограничение диплома."""
    if code == 'radar':
        return is_navigator(position_name) and ship.radar == 'Да'
    if code == 'ecdis':
        return is_navigator(position_name) and ship.electronic_charts == 'Да'
    if code == 'dredger700':
        productivity = _number(ship.productivity)
        return _type_has(ship, 'земснаряд') and productivity is not None and productivity > 700
    if code == 'passenger':
        return _type_has(ship, 'пассажир')
    if code == 'tanker':
        return _type_has(ship, 'наливн', 'танкер')
    if code == 'power330':
        power = _number(ship.engine_power)
        return power is not None and power > 330
    return False


# ==================== ПРОВЕРКА НАЗНАЧЕНИЯ В ШТАТНОЕ РАСПИСАНИЕ ====================

def check_assignment(employee, ship, position, today=None):
    """Список замечаний при назначении сотрудника на должность штатного расписания судна."""
    today = today or date.today()
    issues = []
    position_name = position.name if position else ''

    # Присвоенная отделом кадров должность должна совпадать с должностью по штатному расписанию
    if position and employee.staff_position_id != position.id:
        assigned = employee.staff_position.name if employee.staff_position else 'не указана'
        issues.append(f'Присвоенная должность «{assigned}» не соответствует должности '
                      f'по штатному расписанию «{position_name}»')

    # Ограничения рабочего диплома: по диплому на эту должность, а если его нет — по всем дипломам
    diplomas = [d for d in employee.work_diplomas if position and d.position_id == position.id]
    if not diplomas:
        diplomas = list(employee.work_diplomas)
    for diploma in diplomas:
        title = diploma.position.name if diploma.position else 'без должности'
        if diploma.end_date and diploma.end_date < today:
            issues.append(f'Истёк срок рабочего диплома «{title}» ({diploma.end_date.strftime("%d.%m.%Y")})')
        for code in diploma.restriction_codes:
            if restriction_applies(code, ship, position_name):
                issues.append(f'Рабочий диплом «{title}»: {RESTRICTIONS[code].lower()}')

    # Доп. подготовка с истёкшим сроком
    for training in employee.trainings:
        if training.valid_until and training.valid_until < today:
            title = training.name.name if training.name else 'без наименования'
            issues.append(f'Истёк срок доп. подготовки «{title}» ({training.valid_until.strftime("%d.%m.%Y")})')

    return issues
