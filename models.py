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