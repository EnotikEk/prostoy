from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    full_name = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    ship_id = db.Column(db.Integer, db.ForeignKey('ships.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    ship = db.relationship('Ship', backref='captains', foreign_keys=[ship_id])

class Ship(db.Model):
    __tablename__ = 'ships'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    reg_number = db.Column(db.String(50), unique=True)
    group = db.Column(db.String(1), nullable=False)  # A, B, C
    navigation_start = db.Column(db.Date, nullable=False)
    navigation_end = db.Column(db.Date, nullable=False)
    planned_downtime_hours = db.Column(db.Float, default=0)
    is_active = db.Column(db.Boolean, default=True)

    # Характеристики судна (вводятся пользователем)
    core = db.Column(db.String(10))                # Р.Я / Н.Я
    build_year = db.Column(db.String(20))
    gross_tonnage = db.Column(db.String(50))       # Валовая вместимость, р.т.
    rko_class = db.Column(db.String(100))          # Класс (РКО)
    id_number = db.Column(db.String(100))          # Идентификационный номер
    annual_rko = db.Column(db.String(50))          # Ежегодное РКО
    sub = db.Column(db.String(50))                 # СУБ
    min_crew_cert = db.Column(db.String(200))      # Свидетельство о минимальном составе экипажа
    dimensions = db.Column(db.String(100))         # Габариты L/B/H/T
    branch = db.Column(db.String(200))             # Филиал
    ship_type = db.Column(db.String(200))          # Тип судна
    engine_power = db.Column(db.String(50))        # Мощность главных двигателей, кВт (для земснарядов)
    electronic_charts = db.Column(db.String(3))    # Наличие электронных карт: Да / Нет
    radar = db.Column(db.String(3))                # Наличие радиолокационных станций: Да / Нет
    productivity = db.Column(db.String(50))        # Производительность

class Downtime(db.Model):
    __tablename__ = 'downtimes'
    id = db.Column(db.Integer, primary_key=True)
    ship_id = db.Column(db.Integer, db.ForeignKey('ships.id'), nullable=False)
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime, nullable=True)
    reason_code = db.Column(db.String(2), nullable=True)
    description = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), default='draft')  # draft, captain_signed, approved, rejected
    engineer_comment = db.Column(db.Text, nullable=True)
    engineer_approved = db.Column(db.Boolean, default=False)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    ship = db.relationship('Ship', backref='downtimes')
    creator = db.relationship('User', backref='created_downtimes')
    def get_reason_name(self):
        """Возвращает название причины простоя по коду"""
        from config import Config
        return Config.DOWNTIME_REASONS.get(self.reason_code, '')

class DowntimeFile(db.Model):
    __tablename__ = 'downtime_files'
    id = db.Column(db.Integer, primary_key=True)
    downtime_id = db.Column(db.Integer, db.ForeignKey('downtimes.id'), nullable=False)
    filename = db.Column(db.String(200), nullable=False)
    filepath = db.Column(db.String(500), nullable=False)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    downtime = db.relationship('Downtime', backref='files')

class AuditLog(db.Model):
    __tablename__ = 'audit_logs'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    username = db.Column(db.String(80))
    action = db.Column(db.String(200), nullable=False)
    target_type = db.Column(db.String(50))
    target_id = db.Column(db.Integer)
    details = db.Column(db.Text)
    ip_address = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User', backref='audit_logs')

class PlannedMaintenance(db.Model):
    __tablename__ = 'planned_maintenance'
    id = db.Column(db.Integer, primary_key=True)
    ship_id = db.Column(db.Integer, db.ForeignKey('ships.id'), nullable=False)
    year = db.Column(db.Integer, nullable=False)
    planned_hours = db.Column(db.Float, default=0)

    ship = db.relationship('Ship', backref='maintenance_plans')


# ==================== УЧЁТ ДОКУМЕНТОВ ПЛАВСОСТАВА И АСО ====================

class DictionaryItem(db.Model):
    """Редактируемые выпадающие списки: должности, наименования доп. подготовки."""
    __tablename__ = 'dictionary_items'
    id = db.Column(db.Integer, primary_key=True)
    kind = db.Column(db.String(20), nullable=False, index=True)  # position, training
    name = db.Column(db.String(300), nullable=False)
    sort_order = db.Column(db.Integer, default=0)

    __table_args__ = (db.UniqueConstraint('kind', 'name', name='uq_dictionary_kind_name'),)


class Employee(db.Model):
    """Сотрудник плавсостава."""
    __tablename__ = 'employees'
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(300), nullable=False)
    phone = db.Column(db.String(50))
    staff_position_id = db.Column(db.Integer, db.ForeignKey('dictionary_items.id'))  # Штатная должность (отдел кадров)
    ship_id = db.Column(db.Integer, db.ForeignKey('ships.id'), nullable=True)
    branch = db.Column(db.String(200))     # Филиал, если сотрудник не закреплён за судном
    mppss_date = db.Column(db.Date)        # Подтверждение знаний МППСС — дата выдачи
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    staff_position = db.relationship('DictionaryItem')
    ship = db.relationship('Ship', backref='crew')
    work_diplomas = db.relationship('WorkDiploma', backref='employee', cascade='all, delete-orphan',
                                    order_by='WorkDiploma.id')
    study_diplomas = db.relationship('StudyDiploma', backref='employee', cascade='all, delete-orphan',
                                     order_by='StudyDiploma.id')
    trainings = db.relationship('Training', backref='employee', cascade='all, delete-orphan',
                                order_by='Training.id')
    transfers = db.relationship('EmployeeTransfer', backref='employee', cascade='all, delete-orphan',
                                order_by='EmployeeTransfer.id.desc()')

    @property
    def current_branch(self):
        return self.ship.branch if self.ship else self.branch


class WorkDiploma(db.Model):
    """Рабочий диплом."""
    __tablename__ = 'work_diplomas'
    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    position_id = db.Column(db.Integer, db.ForeignKey('dictionary_items.id'))
    end_date = db.Column(db.Date)
    restrictions = db.Column(db.String(200), default='')  # коды ограничений через запятую

    position = db.relationship('DictionaryItem')

    @property
    def restriction_codes(self):
        return [c for c in (self.restrictions or '').split(',') if c]


class StudyDiploma(db.Model):
    """Учебный диплом."""
    __tablename__ = 'study_diplomas'
    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    level = db.Column(db.String(10), nullable=False)  # ДПО, СПО, ПП, ВПО


class Training(db.Model):
    """Дополнительная подготовка."""
    __tablename__ = 'trainings'
    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    name_id = db.Column(db.Integer, db.ForeignKey('dictionary_items.id'))
    valid_until = db.Column(db.Date)  # Срок

    name = db.relationship('DictionaryItem')


class EmployeeTransfer(db.Model):
    """История переводов сотрудника между судами и филиалами."""
    __tablename__ = 'employee_transfers'
    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    from_ship_id = db.Column(db.Integer, db.ForeignKey('ships.id'))
    to_ship_id = db.Column(db.Integer, db.ForeignKey('ships.id'))
    from_branch = db.Column(db.String(200))
    to_branch = db.Column(db.String(200))
    transfer_date = db.Column(db.Date, nullable=False)
    comment = db.Column(db.String(500))
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    from_ship = db.relationship('Ship', foreign_keys=[from_ship_id])
    to_ship = db.relationship('Ship', foreign_keys=[to_ship_id])
    user = db.relationship('User')


class StaffingPosition(db.Model):
    """Штатное расписание судна: утверждённая должность и назначенный на неё сотрудник."""
    __tablename__ = 'staffing_positions'
    id = db.Column(db.Integer, primary_key=True)
    ship_id = db.Column(db.Integer, db.ForeignKey('ships.id'), nullable=False)
    position_id = db.Column(db.Integer, db.ForeignKey('dictionary_items.id'), nullable=False)
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=True)

    ship = db.relationship('Ship', backref='staffing')
    position = db.relationship('DictionaryItem')
    employee = db.relationship('Employee', backref='staffing_positions')


class RescueEquipment(db.Model):
    """Аварийно-спасательное оборудование (АСО) судна."""
    __tablename__ = 'rescue_equipment'
    id = db.Column(db.Integer, primary_key=True)
    ship_id = db.Column(db.Integer, db.ForeignKey('ships.id'), nullable=False)
    name = db.Column(db.String(300), nullable=False)      # Наименование АСО
    item_number = db.Column(db.String(100))               # Номер изделия (есть не у всех)
    production_date = db.Column(db.Date)                  # Дата производства (есть не у всех)
    contents = db.Column(db.Text)                         # Содержание изделия
    default_quantity = db.Column(db.String(100))          # Исходное кол-во содержимого изделия по умолчанию
    valid_until = db.Column(db.Date)                      # Годен до

    ship = db.relationship('Ship', backref='rescue_equipment')
    transfers = db.relationship('EquipmentTransfer', backref='equipment', cascade='all, delete-orphan')


class EquipmentTransfer(db.Model):
    """История переноса АСО с судна на судно."""
    __tablename__ = 'equipment_transfers'
    id = db.Column(db.Integer, primary_key=True)
    equipment_id = db.Column(db.Integer, db.ForeignKey('rescue_equipment.id'), nullable=False)
    from_ship_id = db.Column(db.Integer, db.ForeignKey('ships.id'), nullable=False)
    to_ship_id = db.Column(db.Integer, db.ForeignKey('ships.id'), nullable=False)
    transfer_date = db.Column(db.Date, nullable=False)
    comment = db.Column(db.String(500))
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    from_ship = db.relationship('Ship', foreign_keys=[from_ship_id])
    to_ship = db.relationship('Ship', foreign_keys=[to_ship_id])
    user = db.relationship('User')


class AsoContract(db.Model):
    """Контракт на проверку АСО."""
    __tablename__ = 'aso_contracts'
    id = db.Column(db.Integer, primary_key=True)
    number = db.Column(db.String(100), nullable=False)
    contract_date = db.Column(db.Date)
    contractor = db.Column(db.String(300))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    prices = db.relationship('AsoPriceItem', backref='contract', cascade='all, delete-orphan',
                             order_by='AsoPriceItem.name')
    invoices = db.relationship('AsoInvoice', backref='contract', cascade='all, delete-orphan',
                               order_by='AsoInvoice.id')


class AsoPriceItem(db.Model):
    """Цена за единицу наименования по контракту."""
    __tablename__ = 'aso_price_items'
    id = db.Column(db.Integer, primary_key=True)
    contract_id = db.Column(db.Integer, db.ForeignKey('aso_contracts.id'), nullable=False)
    name = db.Column(db.String(300), nullable=False)
    unit = db.Column(db.String(30))
    unit_price = db.Column(db.Numeric(12, 2), nullable=False)


class AsoInvoice(db.Model):
    """Выставленный по контракту счёт."""
    __tablename__ = 'aso_invoices'
    id = db.Column(db.Integer, primary_key=True)
    contract_id = db.Column(db.Integer, db.ForeignKey('aso_contracts.id'), nullable=False)
    number = db.Column(db.String(100), nullable=False)
    invoice_date = db.Column(db.Date)
    stated_total = db.Column(db.Numeric(12, 2))  # Итог по счёту

    lines = db.relationship('AsoInvoiceLine', backref='invoice', cascade='all, delete-orphan',
                            order_by='AsoInvoiceLine.id')


class AsoInvoiceLine(db.Model):
    """Строка счёта: наименование из базы цен, количество и сумма, указанная в счёте."""
    __tablename__ = 'aso_invoice_lines'
    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey('aso_invoices.id'), nullable=False)
    price_item_id = db.Column(db.Integer, db.ForeignKey('aso_price_items.id'), nullable=False)
    quantity = db.Column(db.Numeric(12, 3), nullable=False)
    stated_amount = db.Column(db.Numeric(12, 2), nullable=False)

    price_item = db.relationship('AsoPriceItem')