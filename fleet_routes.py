"""Раздел «Суда и документы»: учёт рабочих документов плавсостава и аварийно-спасательного оборудования."""
from collections import defaultdict
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from sqlalchemy import func

from auth import engineer_required, log_audit
from models import (db, Ship, DictionaryItem, Employee, WorkDiploma, StudyDiploma, Training,
                    EmployeeTransfer, StaffingPosition, RescueEquipment, EquipmentTransfer,
                    AsoContract, AsoPriceItem, AsoInvoice, AsoInvoiceLine)
from fleet_rules import (BRANCHES, normalize_branch, branch_order, DEFAULT_POSITIONS, DICTIONARY_KINDS, EDUCATION_LEVELS, RESTRICTIONS,
                         EXPIRY_TITLES, SHIP_CLASSES, parse_date, expiry_level, worst_level,
                         ship_class, ship_doc_level, check_assignment)
from ship_info import CORE_CHOICES

fleet = Blueprint('fleet', __name__, url_prefix='/fleet')


@fleet.before_request
@login_required
@engineer_required
def _require_engineer():
    """Раздел доступен инженеру и администратору."""
    return None


@fleet.app_context_processor
def _inject_fleet_context():
    return {'expiry_titles': EXPIRY_TITLES, 'today_iso': date.today().isoformat()}


@fleet.app_template_filter('money')
def _money(value):
    """1234.5 -> '1 234,50'."""
    if value is None:
        return ''
    return f'{Decimal(value):,.2f}'.replace(',', ' ').replace('.', ',')


@fleet.app_template_filter('qty')
def _qty(value):
    """Количество без лишних нулей: 2.000 -> '2', 1.500 -> '1,5'."""
    if value is None:
        return ''
    text = f'{Decimal(value):f}'
    if '.' in text:
        text = text.rstrip('0').rstrip('.')
    return text.replace('.', ',')


# ==================== ОБЩЕЕ ====================

def seed_dictionaries():
    """Заполняет список должностей значениями из ТЗ при первом запуске."""
    if DictionaryItem.query.filter_by(kind='position').first():
        return
    for order, name in enumerate(DEFAULT_POSITIONS):
        db.session.add(DictionaryItem(kind='position', name=name, sort_order=order))
    db.session.commit()


def dictionary(kind):
    return DictionaryItem.query.filter_by(kind=kind).order_by(DictionaryItem.sort_order, DictionaryItem.name).all()


def branch_names():
    return BRANCHES


def active_ships():
    ships = Ship.query.filter_by(is_active=True).all()
    ships.sort(key=lambda s: (branch_order(s.branch), s.name.lower()))
    return ships


def ship_levels(ships):
    """Подсветка судна: наихудший срок по РКО, СУБ и АСО на борту."""
    aso = defaultdict(list)
    ids = [s.id for s in ships]
    if ids:
        rows = db.session.query(RescueEquipment.ship_id, RescueEquipment.valid_until)\
            .filter(RescueEquipment.ship_id.in_(ids), RescueEquipment.valid_until.isnot(None))
        for ship_id, valid_until in rows:
            aso[ship_id].append(expiry_level(valid_until))
    return {s.id: worst_level([ship_doc_level(s)] + aso[s.id]) for s in ships}


def form_text(name, max_len=None):
    value = (request.form.get(name) or '').strip()
    return value[:max_len] if max_len else value


def form_int(name):
    try:
        return int(request.form.get(name) or '')
    except ValueError:
        return None


def parse_decimal(value):
    text = str(value or '').strip().replace(' ', '').replace('\xa0', '').replace(',', '.')
    if not text:
        return None
    try:
        return Decimal(text)
    except InvalidOperation:
        return None


def dict_item(kind, item_id):
    item = DictionaryItem.query.get(item_id) if item_id else None
    return item if item and item.kind == kind else None


def back(default):
    target = request.form.get('next') or ''
    return redirect(target if target.startswith('/') and not target.startswith('//') else default)


def audit(action, target_type, target_id, details):
    log_audit(current_user.id, current_user.username, action, target_type, target_id, details,
              request.remote_addr)


# ==================== СПИСОК СУДОВ ====================

@fleet.route('/ships')
def ships():
    branch = request.args.get('branch', '')
    core = request.args.get('core', '')
    klass = request.args.get('klass', '')

    query = Ship.query.filter_by(is_active=True)
    if branch:
        query = query.filter(Ship.branch == branch)
    if core:
        query = query.filter(Ship.core == core)
    items = query.all()
    if klass:
        items = [s for s in items if ship_class(s) == klass]
    items.sort(key=lambda s: (branch_order(s.branch), s.name.lower()))

    return render_template('fleet/ships.html',
                           ships=items,
                           levels=ship_levels(items),
                           classes={s.id: ship_class(s) for s in items},
                           branches=branch_names(),
                           core_choices=CORE_CHOICES,
                           ship_classes=SHIP_CLASSES,
                           filters={'branch': branch, 'core': core, 'klass': klass})


# ==================== АСО ====================

@fleet.route('/ship/<int:ship_id>/aso')
def aso(ship_id):
    ship = Ship.query.get_or_404(ship_id)
    items = RescueEquipment.query.filter_by(ship_id=ship.id).order_by(RescueEquipment.name, RescueEquipment.id).all()
    item_levels = {e.id: expiry_level(e.valid_until) for e in items}
    # Наименование оборудования подсвечивается по худшему сроку его изделий
    name_levels = defaultdict(list)
    for e in items:
        name_levels[e.name.strip().lower()].append(item_levels[e.id])
    name_levels = {e.id: worst_level(name_levels[e.name.strip().lower()]) for e in items}
    history = EquipmentTransfer.query.filter(
        (EquipmentTransfer.from_ship_id == ship.id) | (EquipmentTransfer.to_ship_id == ship.id)
    ).order_by(EquipmentTransfer.transfer_date.desc(), EquipmentTransfer.id.desc()).all()
    return render_template('fleet/aso.html', ship=ship, items=items, item_levels=item_levels,
                           name_levels=name_levels, ship_level=ship_levels([ship])[ship.id],
                           history=history, ships=active_ships())


@fleet.route('/ship/<int:ship_id>/aso/save', methods=['POST'])
def aso_save(ship_id):
    ship = Ship.query.get_or_404(ship_id)
    item_id = form_int('equipment_id')
    item = RescueEquipment.query.get_or_404(item_id) if item_id else RescueEquipment(ship_id=ship.id)
    if item.ship_id != ship.id:
        flash('Оборудование относится к другому судну', 'danger')
        return redirect(url_for('fleet.aso', ship_id=ship.id))

    name = form_text('name', 300)
    if not name:
        flash('Укажите наименование АСО', 'danger')
        return redirect(url_for('fleet.aso', ship_id=ship.id))
    production_date = parse_date(request.form.get('production_date'))
    valid_until = parse_date(request.form.get('valid_until'))
    if production_date and valid_until and valid_until < production_date:
        flash('Дата «Годен до» не может быть раньше даты производства', 'danger')
        return redirect(url_for('fleet.aso', ship_id=ship.id))

    item.name = name
    item.item_number = form_text('item_number', 100) or None
    item.production_date = production_date
    item.contents = form_text('contents') or None
    item.default_quantity = form_text('default_quantity', 100) or None
    item.valid_until = valid_until
    if not item_id:
        db.session.add(item)
    db.session.commit()
    audit('edit_aso' if item_id else 'create_aso', 'rescue_equipment', item.id,
          f'АСО «{item.name}» судна {ship.name}')
    flash('АСО сохранено', 'success')
    return redirect(url_for('fleet.aso', ship_id=ship.id))


@fleet.route('/aso/<int:item_id>/delete', methods=['POST'])
def aso_delete(item_id):
    item = RescueEquipment.query.get_or_404(item_id)
    ship_id, name = item.ship_id, item.name
    db.session.delete(item)
    db.session.commit()
    audit('delete_aso', 'rescue_equipment', item_id, f'Удалено АСО «{name}»')
    flash('АСО удалено', 'success')
    return redirect(url_for('fleet.aso', ship_id=ship_id))


@fleet.route('/aso/<int:item_id>/transfer', methods=['POST'])
def aso_transfer(item_id):
    item = RescueEquipment.query.get_or_404(item_id)
    from_ship = item.ship
    to_ship = Ship.query.get(form_int('to_ship_id') or 0)
    transfer_date = parse_date(request.form.get('transfer_date')) or date.today()
    if not to_ship or to_ship.id == from_ship.id:
        flash('Выберите другое судно для переноса', 'danger')
        return redirect(url_for('fleet.aso', ship_id=from_ship.id))

    db.session.add(EquipmentTransfer(equipment_id=item.id, from_ship_id=from_ship.id, to_ship_id=to_ship.id,
                                     transfer_date=transfer_date, comment=form_text('comment', 500) or None,
                                     user_id=current_user.id))
    item.ship_id = to_ship.id
    db.session.commit()
    audit('transfer_aso', 'rescue_equipment', item.id,
          f'АСО «{item.name}» перенесено с судна {from_ship.name} на судно {to_ship.name}')
    flash(f'АСО «{item.name}» перенесено на судно «{to_ship.name}»', 'success')
    return redirect(url_for('fleet.aso', ship_id=from_ship.id))


# ==================== ШТАТНОЕ РАСПИСАНИЕ ====================

@fleet.route('/ship/<int:ship_id>/staffing')
def staffing(ship_id):
    ship = Ship.query.get_or_404(ship_id)
    rows = StaffingPosition.query.filter_by(ship_id=ship.id)\
        .join(DictionaryItem, StaffingPosition.position_id == DictionaryItem.id)\
        .order_by(DictionaryItem.sort_order, DictionaryItem.name, StaffingPosition.id).all()
    issues = {r.id: check_assignment(r.employee, ship, r.position) for r in rows if r.employee}
    crew = Employee.query.filter_by(ship_id=ship.id).order_by(Employee.full_name).all()
    return render_template('fleet/staffing.html', ship=ship, rows=rows, issues=issues, crew=crew,
                           positions=dictionary('position'), ship_level=ship_levels([ship])[ship.id])


@fleet.route('/ship/<int:ship_id>/staffing/save', methods=['POST'])
def staffing_save(ship_id):
    ship = Ship.query.get_or_404(ship_id)
    row_id = form_int('row_id')
    row = StaffingPosition.query.get_or_404(row_id) if row_id else StaffingPosition(ship_id=ship.id)
    position = dict_item('position', form_int('position_id'))
    employee = Employee.query.get(form_int('employee_id') or 0)
    if row.ship_id != ship.id or not position:
        flash('Выберите должность', 'danger')
        return redirect(url_for('fleet.staffing', ship_id=ship.id))
    if employee and employee.ship_id != ship.id:
        flash('Сотрудник не входит в экипаж этого судна', 'danger')
        return redirect(url_for('fleet.staffing', ship_id=ship.id))
    if employee and StaffingPosition.query.filter(StaffingPosition.employee_id == employee.id,
                                                  StaffingPosition.id != (row.id or 0)).first():
        flash(f'{employee.full_name} уже назначен на другую должность штатного расписания', 'danger')
        return redirect(url_for('fleet.staffing', ship_id=ship.id))

    row.position_id = position.id
    row.employee_id = employee.id if employee else None
    if not row_id:
        db.session.add(row)
    db.session.commit()
    audit('edit_staffing', 'staffing', row.id,
          f'Штатное расписание судна {ship.name}: {position.name} — {employee.full_name if employee else "вакансия"}')
    flash('Штатное расписание сохранено', 'success')
    return redirect(url_for('fleet.staffing', ship_id=ship.id))


@fleet.route('/staffing/<int:row_id>/delete', methods=['POST'])
def staffing_delete(row_id):
    row = StaffingPosition.query.get_or_404(row_id)
    ship_id = row.ship_id
    db.session.delete(row)
    db.session.commit()
    audit('delete_staffing', 'staffing', row_id, f'Удалена должность из штатного расписания судна ID {ship_id}')
    flash('Должность удалена из штатного расписания', 'success')
    return redirect(url_for('fleet.staffing', ship_id=ship_id))


@fleet.route('/api/staffing/check')
def staffing_check():
    """Проверка сотрудника перед назначением на должность (предупреждение в окне)."""
    ship = Ship.query.get_or_404(request.args.get('ship_id', type=int))
    employee = Employee.query.get_or_404(request.args.get('employee_id', type=int))
    position = dict_item('position', request.args.get('position_id', type=int))
    return jsonify({'employee': employee.full_name,
                    'issues': check_assignment(employee, ship, position)})


# ==================== ЭКИПАЖ И СОТРУДНИКИ ====================

def employee_form_context():
    return {'positions': dictionary('position'), 'trainings_dict': dictionary('training'),
            'education_levels': EDUCATION_LEVELS, 'restrictions': RESTRICTIONS,
            'ships': active_ships(), 'branches': branch_names()}


@fleet.route('/ship/<int:ship_id>/crew')
def crew(ship_id):
    ship = Ship.query.get_or_404(ship_id)
    employees = Employee.query.filter_by(ship_id=ship.id).order_by(Employee.full_name).all()
    return render_template('fleet/crew.html', ship=ship, employees=employees,
                           ship_level=ship_levels([ship])[ship.id], **employee_form_context())


@fleet.route('/employees')
def employees():
    branch = request.args.get('branch', '')
    ship_id = request.args.get('ship_id', type=int)
    search = request.args.get('q', '').strip()

    items = Employee.query.order_by(Employee.full_name).all()
    if branch:
        items = [e for e in items if e.current_branch == branch]
    if ship_id:
        items = [e for e in items if e.ship_id == ship_id]
    if search:
        items = [e for e in items if search.lower() in e.full_name.lower()]
    return render_template('fleet/employees.html', employees=items,
                           filters={'branch': branch, 'ship_id': ship_id, 'q': search},
                           **employee_form_context())


@fleet.route('/employee/<int:employee_id>')
def employee(employee_id):
    item = Employee.query.get_or_404(employee_id)
    return render_template('fleet/employee.html', employee=item, **employee_form_context())


@fleet.route('/employee/save', methods=['POST'])
def employee_save():
    employee_id = form_int('employee_id')
    item = Employee.query.get_or_404(employee_id) if employee_id else Employee()
    full_name = form_text('full_name', 300)
    if not full_name:
        flash('Укажите ФИО', 'danger')
        return back(url_for('fleet.employees'))

    item.full_name = full_name
    item.phone = form_text('phone', 50) or None
    position = dict_item('position', form_int('staff_position_id'))
    item.staff_position_id = position.id if position else None
    item.mppss_date = parse_date(request.form.get('mppss_date'))
    if not employee_id:
        # Новый сотрудник: судно (из экипажа) или филиал без судна
        ship = Ship.query.get(form_int('ship_id') or 0)
        item.ship_id = ship.id if ship else None
        item.branch = ship.branch if ship else normalize_branch(request.form.get('branch'))
        db.session.add(item)
    db.session.commit()
    audit('edit_employee' if employee_id else 'create_employee', 'employee', item.id, f'Сотрудник {item.full_name}')
    if not employee_id:
        flash('Сотрудник добавлен. Заполните рабочие и учебные дипломы, доп. подготовку.', 'success')
        return redirect(url_for('fleet.employee', employee_id=item.id))
    flash('Сотрудник сохранён', 'success')
    return redirect(url_for('fleet.employee', employee_id=item.id))


@fleet.route('/employee/<int:employee_id>/delete', methods=['POST'])
def employee_delete(employee_id):
    item = Employee.query.get_or_404(employee_id)
    name = item.full_name
    StaffingPosition.query.filter_by(employee_id=item.id).update({'employee_id': None})
    db.session.delete(item)
    db.session.commit()
    audit('delete_employee', 'employee', employee_id, f'Удалён сотрудник {name}')
    flash(f'Сотрудник {name} удалён', 'success')
    return back(url_for('fleet.employees'))


@fleet.route('/employee/<int:employee_id>/transfer', methods=['POST'])
def employee_transfer(employee_id):
    item = Employee.query.get_or_404(employee_id)
    to_ship = Ship.query.get(form_int('to_ship_id') or 0)
    to_branch = to_ship.branch if to_ship else normalize_branch(request.form.get('to_branch'))
    if not to_ship and not to_branch:
        flash('Выберите судно или филиал для перевода', 'danger')
        return back(url_for('fleet.employee', employee_id=item.id))
    if to_ship and to_ship.id == item.ship_id:
        flash('Сотрудник уже в экипаже этого судна', 'warning')
        return back(url_for('fleet.employee', employee_id=item.id))

    from_ship, from_branch = item.ship, item.current_branch
    db.session.add(EmployeeTransfer(
        employee_id=item.id, from_ship_id=from_ship.id if from_ship else None,
        to_ship_id=to_ship.id if to_ship else None, from_branch=from_branch, to_branch=to_branch or None,
        transfer_date=parse_date(request.form.get('transfer_date')) or date.today(),
        comment=form_text('comment', 500) or None, user_id=current_user.id))
    # На прежнем судне должность по штатному расписанию освобождается
    StaffingPosition.query.filter_by(employee_id=item.id).update({'employee_id': None})
    item.ship_id = to_ship.id if to_ship else None
    item.branch = to_branch or None
    db.session.commit()

    target = f'судно «{to_ship.name}»' if to_ship else f'филиал «{to_branch}»'
    audit('transfer_employee', 'employee', item.id,
          f'{item.full_name} переведён с {from_ship.name if from_ship else from_branch or "—"} на {target}')
    flash(f'{item.full_name} переведён на {target}', 'success')
    return back(url_for('fleet.employee', employee_id=item.id))


def _employee_child(model, child_id, employee_id):
    child = model.query.get_or_404(child_id) if child_id else model(employee_id=employee_id)
    if child.employee_id != employee_id:
        return None
    return child


@fleet.route('/employee/<int:employee_id>/work-diploma', methods=['POST'])
def work_diploma_save(employee_id):
    item = Employee.query.get_or_404(employee_id)
    diploma = _employee_child(WorkDiploma, form_int('diploma_id'), item.id)
    position = dict_item('position', form_int('position_id'))
    if diploma is None or not position:
        flash('Укажите должность рабочего диплома', 'danger')
        return redirect(url_for('fleet.employee', employee_id=item.id))
    diploma.position_id = position.id
    diploma.end_date = parse_date(request.form.get('end_date'))
    diploma.restrictions = ','.join(c for c in request.form.getlist('restrictions') if c in RESTRICTIONS)
    db.session.add(diploma)
    db.session.commit()
    audit('edit_work_diploma', 'employee', item.id, f'Рабочий диплом «{position.name}» — {item.full_name}')
    flash('Рабочий диплом сохранён', 'success')
    return redirect(url_for('fleet.employee', employee_id=item.id))


@fleet.route('/employee/<int:employee_id>/study-diploma', methods=['POST'])
def study_diploma_save(employee_id):
    item = Employee.query.get_or_404(employee_id)
    diploma = _employee_child(StudyDiploma, form_int('diploma_id'), item.id)
    level = form_text('level')
    if diploma is None or level not in EDUCATION_LEVELS:
        flash('Выберите уровень образования', 'danger')
        return redirect(url_for('fleet.employee', employee_id=item.id))
    diploma.level = level
    db.session.add(diploma)
    db.session.commit()
    audit('edit_study_diploma', 'employee', item.id, f'Учебный диплом {level} — {item.full_name}')
    flash('Учебный диплом сохранён', 'success')
    return redirect(url_for('fleet.employee', employee_id=item.id))


@fleet.route('/employee/<int:employee_id>/training', methods=['POST'])
def training_save(employee_id):
    item = Employee.query.get_or_404(employee_id)
    training = _employee_child(Training, form_int('training_id'), item.id)
    name = dict_item('training', form_int('name_id'))
    if training is None or not name:
        flash('Выберите наименование доп. подготовки', 'danger')
        return redirect(url_for('fleet.employee', employee_id=item.id))
    training.name_id = name.id
    training.valid_until = parse_date(request.form.get('valid_until'))
    db.session.add(training)
    db.session.commit()
    audit('edit_training', 'employee', item.id, f'Доп. подготовка «{name.name}» — {item.full_name}')
    flash('Доп. подготовка сохранена', 'success')
    return redirect(url_for('fleet.employee', employee_id=item.id))


_CHILD_MODELS = {'work-diploma': WorkDiploma, 'study-diploma': StudyDiploma, 'training': Training}


@fleet.route('/employee/<kind>/<int:child_id>/delete', methods=['POST'])
def employee_child_delete(kind, child_id):
    model = _CHILD_MODELS.get(kind)
    if model is None:
        return redirect(url_for('fleet.employees'))
    child = model.query.get_or_404(child_id)
    employee_id = child.employee_id
    db.session.delete(child)
    db.session.commit()
    audit(f'delete_{kind}', 'employee', employee_id, f'Удалена запись ({kind}) ID {child_id}')
    flash('Запись удалена', 'success')
    return redirect(url_for('fleet.employee', employee_id=employee_id))


# ==================== СПРАВОЧНИКИ ====================

@fleet.route('/dictionaries')
def dictionaries():
    items = {kind: dictionary(kind) for kind in DICTIONARY_KINDS}
    used = set()
    for column in (Employee.staff_position_id, WorkDiploma.position_id, StaffingPosition.position_id, Training.name_id):
        used |= {v for (v,) in db.session.query(column).filter(column.isnot(None)).distinct()}
    return render_template('fleet/dictionaries.html', kinds=DICTIONARY_KINDS, items=items, used=used)


@fleet.route('/dictionary/save', methods=['POST'])
def dictionary_save():
    kind = form_text('kind')
    name = form_text('name', 300)
    item_id = form_int('item_id')
    if kind not in DICTIONARY_KINDS or not name:
        flash('Укажите наименование', 'danger')
        return redirect(url_for('fleet.dictionaries'))
    duplicate = DictionaryItem.query.filter(DictionaryItem.kind == kind,
                                            func.lower(DictionaryItem.name) == name.lower(),
                                            DictionaryItem.id != (item_id or 0)).first()
    if duplicate:
        flash(f'«{name}» уже есть в списке', 'warning')
        return redirect(url_for('fleet.dictionaries'))

    if item_id:
        item = DictionaryItem.query.get_or_404(item_id)
        old_name, item.name = item.name, name
        details = f'Переименовано «{old_name}» → «{name}» ({DICTIONARY_KINDS[kind]})'
    else:
        max_order = db.session.query(func.max(DictionaryItem.sort_order)).filter_by(kind=kind).scalar() or 0
        item = DictionaryItem(kind=kind, name=name, sort_order=max_order + 1)
        db.session.add(item)
        details = f'Добавлено «{name}» ({DICTIONARY_KINDS[kind]})'
    db.session.commit()
    audit('edit_dictionary', 'dictionary', item.id, details)
    flash('Справочник обновлён', 'success')
    return redirect(url_for('fleet.dictionaries'))


@fleet.route('/dictionary/<int:item_id>/delete', methods=['POST'])
def dictionary_delete(item_id):
    item = DictionaryItem.query.get_or_404(item_id)
    in_use = any(db.session.query(column).filter(column == item.id).first()
                 for column in (Employee.staff_position_id, WorkDiploma.position_id,
                                StaffingPosition.position_id, Training.name_id))
    if in_use:
        flash(f'«{item.name}» используется и не может быть удалено. Его можно переименовать.', 'danger')
        return redirect(url_for('fleet.dictionaries'))
    db.session.delete(item)
    db.session.commit()
    audit('delete_dictionary', 'dictionary', item_id, f'Удалено «{item.name}»')
    flash('Запись удалена из справочника', 'success')
    return redirect(url_for('fleet.dictionaries'))


# ==================== КОНТРАКТЫ ПО АСО ====================

CENT = Decimal('0.01')


def invoice_summary(invoice):
    """Расчёт счёта по ценам контракта и сверка с суммами, указанными в счёте."""
    lines = []
    for line in invoice.lines:
        expected = (line.quantity * line.price_item.unit_price).quantize(CENT, ROUND_HALF_UP)
        lines.append({'line': line, 'expected': expected, 'diff': line.stated_amount - expected})
    expected_total = sum((l['expected'] for l in lines), Decimal('0.00'))
    stated_lines_total = sum((l['line'].stated_amount for l in lines), Decimal('0.00'))
    stated_total = invoice.stated_total
    total_diff = (stated_total - expected_total) if stated_total is not None else None
    correct = all(l['diff'] == 0 for l in lines) and (total_diff is None or total_diff == 0)
    return {'lines': lines, 'expected_total': expected_total, 'stated_lines_total': stated_lines_total,
            'stated_total': stated_total, 'total_diff': total_diff, 'correct': correct}


@fleet.route('/contracts')
def contracts():
    items = AsoContract.query.order_by(AsoContract.contract_date.desc(), AsoContract.id.desc()).all()
    return render_template('fleet/contracts.html', contracts=items)


@fleet.route('/contract/save', methods=['POST'])
def contract_save():
    contract_id = form_int('contract_id')
    item = AsoContract.query.get_or_404(contract_id) if contract_id else AsoContract()
    number = form_text('number', 100)
    if not number:
        flash('Укажите номер контракта', 'danger')
        return back(url_for('fleet.contracts'))
    item.number = number
    item.contract_date = parse_date(request.form.get('contract_date'))
    item.contractor = form_text('contractor', 300) or None
    db.session.add(item)
    db.session.commit()
    audit('edit_aso_contract', 'aso_contract', item.id, f'Контракт по АСО № {item.number}')
    flash('Контракт сохранён', 'success')
    return redirect(url_for('fleet.contract', contract_id=item.id))


@fleet.route('/contract/<int:contract_id>')
def contract(contract_id):
    item = AsoContract.query.get_or_404(contract_id)
    return render_template('fleet/contract.html', contract=item,
                           summaries={inv.id: invoice_summary(inv) for inv in item.invoices})


@fleet.route('/contract/<int:contract_id>/delete', methods=['POST'])
def contract_delete(contract_id):
    item = AsoContract.query.get_or_404(contract_id)
    number = item.number
    db.session.delete(item)
    db.session.commit()
    audit('delete_aso_contract', 'aso_contract', contract_id, f'Удалён контракт по АСО № {number}')
    flash('Контракт удалён', 'success')
    return redirect(url_for('fleet.contracts'))


@fleet.route('/contract/<int:contract_id>/price', methods=['POST'])
def price_save(contract_id):
    item = AsoContract.query.get_or_404(contract_id)
    price_id = form_int('price_id')
    price = AsoPriceItem.query.get_or_404(price_id) if price_id else AsoPriceItem(contract_id=item.id)
    name = form_text('name', 300)
    unit_price = parse_decimal(request.form.get('unit_price'))
    if price.contract_id != item.id or not name or unit_price is None or unit_price < 0:
        flash('Укажите наименование и цену за единицу', 'danger')
        return redirect(url_for('fleet.contract', contract_id=item.id))
    price.name = name
    price.unit = form_text('unit', 30) or None
    price.unit_price = unit_price.quantize(CENT, ROUND_HALF_UP)
    db.session.add(price)
    db.session.commit()
    audit('edit_aso_price', 'aso_contract', item.id, f'Цена «{price.name}»: {price.unit_price}')
    flash('Цена сохранена', 'success')
    return redirect(url_for('fleet.contract', contract_id=item.id))


@fleet.route('/price/<int:price_id>/delete', methods=['POST'])
def price_delete(price_id):
    price = AsoPriceItem.query.get_or_404(price_id)
    contract_id = price.contract_id
    if AsoInvoiceLine.query.filter_by(price_item_id=price.id).first():
        flash(f'Наименование «{price.name}» есть в счетах и не может быть удалено', 'danger')
        return redirect(url_for('fleet.contract', contract_id=contract_id))
    db.session.delete(price)
    db.session.commit()
    audit('delete_aso_price', 'aso_contract', contract_id, f'Удалена цена «{price.name}»')
    flash('Наименование удалено', 'success')
    return redirect(url_for('fleet.contract', contract_id=contract_id))


@fleet.route('/contract/<int:contract_id>/invoice', methods=['POST'])
def invoice_save(contract_id):
    item = AsoContract.query.get_or_404(contract_id)
    invoice_id = form_int('invoice_id')
    invoice = AsoInvoice.query.get_or_404(invoice_id) if invoice_id else AsoInvoice(contract_id=item.id)
    number = form_text('number', 100)
    stated_total = parse_decimal(request.form.get('stated_total'))
    if invoice.contract_id != item.id or not number:
        flash('Укажите номер счёта', 'danger')
        return redirect(url_for('fleet.contract', contract_id=item.id))
    if request.form.get('stated_total', '').strip() and stated_total is None:
        flash('Итог по счёту указан неверно', 'danger')
        return redirect(url_for('fleet.contract', contract_id=item.id))
    invoice.number = number
    invoice.invoice_date = parse_date(request.form.get('invoice_date'))
    invoice.stated_total = stated_total.quantize(CENT, ROUND_HALF_UP) if stated_total is not None else None
    db.session.add(invoice)
    db.session.commit()
    audit('edit_aso_invoice', 'aso_invoice', invoice.id, f'Счёт № {invoice.number} по контракту № {item.number}')
    flash('Счёт сохранён', 'success')
    return redirect(url_for('fleet.invoice', invoice_id=invoice.id))


@fleet.route('/invoice/<int:invoice_id>')
def invoice(invoice_id):
    item = AsoInvoice.query.get_or_404(invoice_id)
    return render_template('fleet/invoice.html', invoice=item, summary=invoice_summary(item))


@fleet.route('/invoice/<int:invoice_id>/delete', methods=['POST'])
def invoice_delete(invoice_id):
    item = AsoInvoice.query.get_or_404(invoice_id)
    contract_id, number = item.contract_id, item.number
    db.session.delete(item)
    db.session.commit()
    audit('delete_aso_invoice', 'aso_invoice', invoice_id, f'Удалён счёт № {number}')
    flash('Счёт удалён', 'success')
    return redirect(url_for('fleet.contract', contract_id=contract_id))


@fleet.route('/invoice/<int:invoice_id>/line', methods=['POST'])
def invoice_line_save(invoice_id):
    item = AsoInvoice.query.get_or_404(invoice_id)
    line_id = form_int('line_id')
    line = AsoInvoiceLine.query.get_or_404(line_id) if line_id else AsoInvoiceLine(invoice_id=item.id)
    price = AsoPriceItem.query.get(form_int('price_item_id') or 0)
    quantity = parse_decimal(request.form.get('quantity'))
    stated_amount = parse_decimal(request.form.get('stated_amount'))
    if (line.invoice_id != item.id or not price or price.contract_id != item.contract_id
            or quantity is None or quantity <= 0 or stated_amount is None):
        flash('Укажите наименование из базы цен, количество и сумму по счёту', 'danger')
        return redirect(url_for('fleet.invoice', invoice_id=item.id))
    line.price_item_id = price.id
    line.quantity = quantity
    line.stated_amount = stated_amount.quantize(CENT, ROUND_HALF_UP)
    db.session.add(line)
    db.session.commit()
    flash('Строка счёта сохранена', 'success')
    return redirect(url_for('fleet.invoice', invoice_id=item.id))


@fleet.route('/invoice-line/<int:line_id>/delete', methods=['POST'])
def invoice_line_delete(line_id):
    line = AsoInvoiceLine.query.get_or_404(line_id)
    invoice_id = line.invoice_id
    db.session.delete(line)
    db.session.commit()
    flash('Строка удалена', 'success')
    return redirect(url_for('fleet.invoice', invoice_id=invoice_id))
