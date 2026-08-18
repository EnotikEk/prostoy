from flask import session, redirect, url_for, flash, request
from flask_login import LoginManager, login_user, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from models import User, db, AuditLog
from config import Config
from functools import wraps

login_manager = LoginManager()

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def init_auth(app):
    login_manager.init_app(app)
    login_manager.login_view = 'login'  # ИСПРАВЛЕНО: было 'login_page'

def login_user_by_credentials(username, password, ip_address):
    user = User.query.filter_by(username=username, is_active=True).first()
    if user and check_password_hash(user.password_hash, password):
        login_user(user)
        log_audit(user.id, user.username, 'login', 'user', user.id, 
                  f'Успешный вход в систему', ip_address)
        return True
    return False

def logout_user_and_log(ip_address):
    if current_user.is_authenticated:
        log_audit(current_user.id, current_user.username, 'logout', 'user', 
                  current_user.id, 'Выход из системы', ip_address)
    logout_user()

def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                flash('Пожалуйста, авторизуйтесь', 'warning')
                return redirect(url_for('login'))  # ИСПРАВЛЕНО
            if current_user.role not in roles:
                flash('У вас нет доступа к этой странице', 'danger')
                return redirect(url_for('dashboard'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def captain_required(f):
    return role_required(Config.ROLE_CAPTAIN, Config.ROLE_ENGINEER, Config.ROLE_ADMIN)(f)

def engineer_required(f):
    return role_required(Config.ROLE_ENGINEER, Config.ROLE_ADMIN)(f)

def admin_required(f):
    return role_required(Config.ROLE_ADMIN)(f)

def log_audit(user_id, username, action, target_type, target_id, details, ip_address):
    try:
        log = AuditLog(
            user_id=user_id,
            username=username,
            action=action,
            target_type=target_type,
            target_id=target_id,
            details=details,
            ip_address=ip_address
        )
        db.session.add(log)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"Audit log error: {e}")

def create_default_users():
    if User.query.count() == 0:
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
        
        db.session.commit()
        print("Созданы пользователи по умолчанию: admin/admin123, engineer/eng123")