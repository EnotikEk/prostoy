import time

from flask import session, redirect, url_for, flash, request, jsonify
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
    login_manager.login_message = 'Пожалуйста, войдите в систему'
    login_manager.login_message_category = 'warning'

def login_user_by_credentials(username, password, ip_address):
    user = User.query.filter_by(username=username, is_active=True).first()
    if user and check_password_hash(user.password_hash, password):
        session.clear()
        login_user(user, remember=False)
        session['last_activity'] = time.time()
        session['fresh_login'] = True  # браузер отметит вкладку, в которой выполнен вход
        log_audit(user.id, user.username, 'login', 'user', user.id, 
                  f'Успешный вход в систему', ip_address)
        return True
    return False

LOGOUT_REASONS = {
    'idle': 'Автоматический выход: бездействие',
    'tab_closed': 'Автоматический выход: вкладка была закрыта',
}


def logout_user_and_log(ip_address, reason=None):
    if current_user.is_authenticated:
        log_audit(current_user.id, current_user.username, 'logout', 'user',
                  current_user.id, LOGOUT_REASONS.get(reason, 'Выход из системы'), ip_address)
    logout_user()
    session.clear()


def enforce_idle_timeout():
    """before_request: выход, если от пользователя не было запросов дольше SESSION_IDLE_MINUTES."""
    if request.endpoint == 'static' or not current_user.is_authenticated:
        return None
    now = time.time()
    last = session.get('last_activity')
    if last is not None and now - last > Config.SESSION_IDLE_MINUTES * 60:
        logout_user_and_log(request.remote_addr, 'idle')
        flash(f'Сеанс завершён: нет действий более {Config.SESSION_IDLE_MINUTES} минут. Войдите снова.', 'warning')
        if (request.path.startswith('/api/') or request.path.startswith('/fleet/api/')
                or request.endpoint in ('session_ping', 'session_status')):
            return jsonify({'error': 'session_expired'}), 401
        return redirect(url_for('login'))
    # Проверка состояния сеанса из браузера не считается действием пользователя и не продлевает сеанс
    if request.endpoint != 'session_status':
        session['last_activity'] = now
    return None


def session_seconds_left():
    last = session.get('last_activity') or time.time()
    return max(0, int(Config.SESSION_IDLE_MINUTES * 60 - (time.time() - last)))

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