from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash
from datetime import datetime, timedelta
import os

# Создаем минимальное приложение Flask
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///fleet.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Определяем модели (копия из models.py)
class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    full_name = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    ship_id = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Ship(db.Model):
    __tablename__ = 'ships'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    reg_number = db.Column(db.String(50), unique=True)
    group = db.Column(db.String(1), nullable=False)
    navigation_start = db.Column(db.Date, nullable=False)
    navigation_end = db.Column(db.Date, nullable=False)
    planned_downtime_hours = db.Column(db.Float, default=0)
    is_active = db.Column(db.Boolean, default=True)

class Downtime(db.Model):
    __tablename__ = 'downtimes'
    id = db.Column(db.Integer, primary_key=True)
    ship_id = db.Column(db.Integer, db.ForeignKey('ships.id'), nullable=False)
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime, nullable=True)
    reason_code = db.Column(db.String(2), nullable=True)
    description = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), default='draft')
    engineer_comment = db.Column(db.Text, nullable=True)
    engineer_approved = db.Column(db.Boolean, default=False)
    created_by = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class PlannedMaintenance(db.Model):
    __tablename__ = 'planned_maintenance'
    id = db.Column(db.Integer, primary_key=True)
    ship_id = db.Column(db.Integer, db.ForeignKey('ships.id'), nullable=False)
    year = db.Column(db.Integer, nullable=False)
    planned_hours = db.Column(db.Float, default=0)

class AuditLog(db.Model):
    __tablename__ = 'audit_logs'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=True)
    username = db.Column(db.String(80))
    action = db.Column(db.String(200), nullable=False)
    target_type = db.Column(db.String(50))
    target_id = db.Column(db.Integer)
    details = db.Column(db.Text)
    ip_address = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class DowntimeFile(db.Model):
    __tablename__ = 'downtime_files'
    id = db.Column(db.Integer, primary_key=True)
    downtime_id = db.Column(db.Integer, db.ForeignKey('downtimes.id'), nullable=False)
    filename = db.Column(db.String(200), nullable=False)
    filepath = db.Column(db.String(500), nullable=False)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)

# Создаем таблицы и данные
with app.app_context():
    print("=" * 60)
    print("СОЗДАНИЕ БАЗЫ ДАННЫХ")
    print("=" * 60)
    
    # Удаляем старую БД если есть
    if os.path.exists('fleet.db'):
        os.remove('fleet.db')
        print("✅ Удален старый fleet.db")
    
    # Создаем все таблицы
    db.create_all()
    print("✅ Созданы таблицы")
    
    # Создаем пользователей
    admin = User(
        username='admin',
        password_hash=generate_password_hash('admin123'),
        full_name='Системный администратор',
        role='admin',
        is_active=True
    )
    db.session.add(admin)
    
    engineer = User(
        username='engineer',
        password_hash=generate_password_hash('eng123'),
        full_name='Главный инженер',
        role='engineer',
        is_active=True
    )
    db.session.add(engineer)
    
    captain = User(
        username='captain',
        password_hash=generate_password_hash('capt123'),
        full_name='Капитан',
        role='captain',
        is_active=True
    )
    db.session.add(captain)
    db.session.commit()
    print("✅ Созданы пользователи: admin, engineer, captain")
    
    # Создаем судно
    ship = Ship(
        name='Рабочее судно',
        reg_number='WORK-001',
        group='A',
        navigation_start=datetime(2026, 1, 1),
        navigation_end=datetime(2026, 12, 31),
        planned_downtime_hours=4320,
        is_active=True
    )
    db.session.add(ship)
    db.session.commit()
    print(f"✅ Создано судно: {ship.name} (группа A)")
    
    # Привязываем капитана
    captain.ship_id = ship.id
    db.session.commit()
    print(f"✅ Капитан привязан к судну")
    
    # Создаем простой
    downtime = Downtime(
        ship_id=ship.id,
        start_time=datetime.now() - timedelta(hours=2),
        end_time=datetime.now(),
        reason_code='01',
        description='Тестовый простой на 2 часа',
        status='approved',
        engineer_approved=True,
        created_by=captain.id
    )
    db.session.add(downtime)
    db.session.commit()
    print(f"✅ Создан утвержденный простой на 2 часа")
    
    print("\n" + "=" * 60)
    print("ГОТОВО! База данных создана")
    print("=" * 60)
    print("\n🔑 Данные для входа:")
    print("   👑 Администратор: admin / admin123")
    print("   🔧 Инженер: engineer / eng123")
    print("   ⚓ Капитан: captain / capt123")