from datetime import datetime, timedelta
from flask import Flask, render_template, redirect, url_for, flash, request, jsonify, send_file
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash
import os
import mimetypes

from config import Config
from models import db, User, Ship, Downtime, PlannedMaintenance, DowntimeFile, AuditLog
from auth import init_auth, login_user_by_credentials, logout_user_and_log, log_audit, create_default_users
from auth import captain_required, engineer_required, admin_required
from kpi_calculator import KPICalculator
from report_generator import ReportGenerator
from file_uploader import FileUploader
from utils import validate_description, calculate_duration_hours
from ship_info import SHIP_FIELDS, CORE_CHOICES, REFERENCE, find_reference, get_ship_info, has_ship_info, ensure_ship_columns

app = Flask(__name__)
app.config.from_object(Config)

# Инициализация
db.init_app(app)
init_auth(app)

# Создание папок
os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)
os.makedirs('reports', exist_ok=True)

# Создание таблиц БД
with app.app_context():
    db.create_all()
    ensure_ship_columns(db)
    create_default_users()

# ==================== ОБЩИЕ МАРШРУТЫ ====================

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if login_user_by_credentials(username, password, request.remote_addr):
            return redirect(url_for('dashboard'))
        else:
            flash('Неверное имя пользователя или пароль', 'danger')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user_and_log(request.remote_addr)
    flash('Вы вышли из системы', 'info')
    return redirect(url_for('login'))

@app.route('/')
@login_required
def dashboard():
    if current_user.role == 'captain':
        return redirect(url_for('captain_dashboard'))
    elif current_user.role == 'engineer':
        return redirect(url_for('engineer_dashboard_page'))
    else:
        return redirect(url_for('admin_users'))

# ==================== ЗАГРУЗКА ФАЙЛОВ ====================

@app.route('/uploads/<filename>')
@login_required
def uploaded_file(filename):
    file_path = os.path.join(Config.UPLOAD_FOLDER, filename)
    
    if not os.path.exists(file_path):
        flash(f'Файл {filename} не найден', 'danger')
        return redirect(request.referrer or url_for('dashboard'))
    
    mime_type, encoding = mimetypes.guess_type(file_path)
    if mime_type is None:
        ext = os.path.splitext(filename)[1].lower()
        mime_map = {
            '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
            '.gif': 'image/gif', '.bmp': 'image/bmp', '.pdf': 'application/pdf',
            '.doc': 'application/msword', '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            '.txt': 'text/plain'
        }
        mime_type = mime_map.get(ext, 'application/octet-stream')
    
    response = send_file(file_path, mimetype=mime_type, as_attachment=False)
    if mime_type and mime_type.startswith('image/'):
        response.headers['Cache-Control'] = 'public, max-age=31536000'
    
    return response

# ==================== КАПИТАН ====================

@app.route('/captain/dashboard')
@login_required
@captain_required
def captain_dashboard():
    ship = None
    if current_user.ship_id:
        ship = Ship.query.get(current_user.ship_id)
    
    active_downtime = None
    if ship:
        active_downtime = Downtime.query.filter_by(
            ship_id=ship.id, end_time=None, status='draft'
        ).first()
    
    recent_downtimes = []
    if ship:
        recent_downtimes = Downtime.query.filter_by(ship_id=ship.id)\
            .order_by(Downtime.created_at.desc()).limit(5).all()
    
    return render_template('captain/dashboard.html', 
                         ship=ship, 
                         active_downtime=active_downtime,
                         recent_downtimes=recent_downtimes)

@app.route('/captain/downtime/start', methods=['POST'])
@login_required
@captain_required
def start_downtime():
    try:
        if not current_user.ship_id:
            flash('Вы не привязаны к судну', 'danger')
            return redirect(url_for('captain_dashboard'))
        
        active = Downtime.query.filter_by(
            ship_id=current_user.ship_id, end_time=None, status='draft'
        ).first()
        
        if active:
            flash('Уже есть активный простой. Завершите его сначала.', 'warning')
            return redirect(url_for('captain_dashboard'))
        
        downtime = Downtime(
            ship_id=current_user.ship_id,
            start_time=datetime.now(),
            status='draft',
            created_by=current_user.id
        )
        db.session.add(downtime)
        db.session.commit()
        
        log_audit(current_user.id, current_user.username, 'start_downtime', 'downtime', 
                  downtime.id, f'Начат простой для судна ID {current_user.ship_id}', request.remote_addr)
        
        flash('Простой начат', 'success')
        return redirect(url_for('captain_dashboard'))
        
    except Exception as e:
        db.session.rollback()
        flash('Ошибка при начале простоя', 'danger')
        return redirect(url_for('captain_dashboard'))

@app.route('/captain/downtime/<int:downtime_id>/complete', methods=['POST'])
@login_required
@captain_required
def complete_downtime(downtime_id):
    try:
        downtime = Downtime.query.get_or_404(downtime_id)
        
        if downtime.ship_id != current_user.ship_id:
            flash('Доступ запрещён', 'danger')
            return redirect(url_for('captain_dashboard'))
        
        if downtime.end_time is not None:
            flash('Этот простой уже завершён', 'warning')
            return redirect(url_for('captain_dashboard'))
        
        reason_code = request.form.get('reason_code')
        description = request.form.get('description')
        
        if not reason_code:
            flash('Выберите причину простоя', 'danger')
            return redirect(url_for('captain_dashboard'))
        
        if not description or len(description.strip()) < 10:
            flash('Описание должно содержать не менее 10 символов', 'danger')
            return redirect(url_for('captain_dashboard'))
        
        downtime.end_time = datetime.now()
        downtime.reason_code = reason_code
        downtime.description = description
        downtime.status = 'captain_signed'
        
        db.session.commit()
        
        files = request.files.getlist('files')
        if files and files[0].filename:
            FileUploader.save_files(files, downtime.id)
        
        log_audit(current_user.id, current_user.username, 'complete_downtime', 'downtime', 
                  downtime.id, f'Завершён простой. Причина: {reason_code}', request.remote_addr)
        
        flash('Простой завершён и отправлен на утверждение', 'success')
        return redirect(url_for('captain_dashboard'))
        
    except Exception as e:
        db.session.rollback()
        flash('Ошибка при завершении простоя', 'danger')
        return redirect(url_for('captain_dashboard'))

@app.route('/captain/downtime/<int:downtime_id>/cancel', methods=['POST'])
@login_required
@captain_required
def cancel_downtime(downtime_id):
    try:
        downtime = Downtime.query.get_or_404(downtime_id)
        
        if downtime.ship_id != current_user.ship_id:
            flash('Доступ запрещён', 'danger')
            return redirect(url_for('captain_dashboard'))
        
        if downtime.end_time is not None:
            flash('Нельзя отменить завершённый простой', 'warning')
            return redirect(url_for('captain_dashboard'))
        
        db.session.delete(downtime)
        db.session.commit()
        
        log_audit(current_user.id, current_user.username, 'cancel_downtime', 'downtime', 
                  downtime.id, 'Отмена простоя', request.remote_addr)
        
        flash('Простой отменён', 'success')
        return redirect(url_for('captain_dashboard'))
        
    except Exception as e:
        db.session.rollback()
        flash('Ошибка при отмене простоя', 'danger')
        return redirect(url_for('captain_dashboard'))

@app.route('/captain/history')
@login_required
@captain_required
def captain_history():
    ship_id = current_user.ship_id
    if not ship_id:
        return render_template('captain/history.html', downtimes=[])
    
    status_filter = request.args.get('status', '')
    reason_filter = request.args.get('reason', '')
    
    query = Downtime.query.filter_by(ship_id=ship_id)
    
    if status_filter:
        query = query.filter_by(status=status_filter)
    if reason_filter:
        query = query.filter_by(reason_code=reason_filter)
    
    downtimes = query.order_by(Downtime.start_time.desc()).all()
    
    return render_template('captain/history.html', 
                         downtimes=downtimes,
                         status_filter=status_filter,
                         reason_filter=reason_filter)

# ==================== ИНЖЕНЕР ====================

@app.route('/engineer/pending')
@login_required
@engineer_required
def engineer_pending():
    pending_downtimes = Downtime.query.filter_by(status='captain_signed')\
        .join(Ship).filter(Ship.group == 'A')\
        .order_by(Downtime.start_time.desc()).all()
    
    return render_template('engineer/pending.html', downtimes=pending_downtimes)

@app.route('/engineer/downtime/<int:downtime_id>/approve', methods=['POST'])
@login_required
@engineer_required
def approve_downtime(downtime_id):
    downtime = Downtime.query.get_or_404(downtime_id)
    downtime.status = 'approved'
    downtime.engineer_approved = True
    db.session.commit()
    
    log_audit(current_user.id, current_user.username, 'approve_downtime', 'downtime', 
              downtime.id, f'Утверждён простой для судна ID {downtime.ship_id}', request.remote_addr)
    
    flash('Простой утверждён', 'success')
    return redirect(url_for('engineer_pending'))

@app.route('/engineer/downtime/<int:downtime_id>/reject', methods=['POST'])
@login_required
@engineer_required
def reject_downtime(downtime_id):
    downtime = Downtime.query.get_or_404(downtime_id)
    comment = request.form.get('comment', '')
    
    if not comment:
        flash('Укажите причину отклонения', 'danger')
        return redirect(url_for('engineer_pending'))
    
    downtime.status = 'rejected'
    downtime.engineer_approved = False
    downtime.engineer_comment = comment
    db.session.commit()
    
    log_audit(current_user.id, current_user.username, 'reject_downtime', 'downtime', 
              downtime.id, f'Отклонён простой. Причина: {comment}', request.remote_addr)
    
    flash('Простой отклонён', 'success')
    return redirect(url_for('engineer_pending'))

@app.route('/engineer/dashboard')
@login_required
@engineer_required
def engineer_dashboard_page():
    db.session.expire_all()
    
    current_year = datetime.now().year
    start_date = datetime(current_year, 1, 1)
    end_date = datetime.now()
    
    kpi_data = KPICalculator.calculate_kpi_group_a(current_year)
    structure = KPICalculator.get_downtime_structure(start_date=start_date, end_date=end_date)
    
    return render_template('engineer/dashboard.html', 
                         kpi_data=kpi_data,
                         structure=structure,
                         now=datetime.now())

@app.route('/engineer/downtimes')
@login_required
@engineer_required
def engineer_downtimes():
    ship_filter = request.args.get('ship_id', '')
    status_filter = request.args.get('status', '')
    reason_filter = request.args.get('reason', '')
    
    query = Downtime.query
    
    if ship_filter:
        query = query.filter_by(ship_id=ship_filter)
    if status_filter:
        query = query.filter_by(status=status_filter)
    if reason_filter:
        query = query.filter_by(reason_code=reason_filter)
    
    downtimes = query.order_by(Downtime.start_time.desc()).all()
    ships = Ship.query.all()
    
    return render_template('engineer/downtimes.html', 
                         downtimes=downtimes,
                         ships=ships)

@app.route('/engineer/report/<int:quarter>/<int:year>')
@login_required
@engineer_required
def generate_report(quarter, year):
    try:
        filepath = ReportGenerator.generate_quarterly_report(quarter, year)
        log_audit(current_user.id, current_user.username, 'generate_report', 'report', 
                  0, f'Сгенерирован отчёт за {quarter} кв {year} г.', request.remote_addr)
        return send_file(filepath, as_attachment=True)
    except Exception as e:
        flash(f'Ошибка генерации отчёта: {str(e)}', 'danger')
        return redirect(url_for('engineer_dashboard_page'))

# ==================== АДМИНИСТРАТОР ====================

@app.route('/admin/downtimes/correction')
@login_required
@admin_required
def admin_downtimes_correction():
    ship_filter = request.args.get('ship_id', '')
    status_filter = request.args.get('status', '')
    
    query = Downtime.query
    
    if ship_filter:
        query = query.filter_by(ship_id=ship_filter)
    if status_filter:
        query = query.filter_by(status=status_filter)
    
    downtimes = query.order_by(Downtime.start_time.desc()).all()
    ships = Ship.query.all()
    
    return render_template('admin/downtimes_correction.html', downtimes=downtimes, ships=ships)

@app.route('/admin/downtime/<int:downtime_id>/correct', methods=['POST'])
@login_required
@admin_required
def admin_downtime_correct(downtime_id):
    downtime = Downtime.query.get_or_404(downtime_id)
    correction_reason = request.form.get('correction_reason', '')
    
    if not correction_reason:
        flash('Укажите причину корректировки', 'danger')
        return redirect(url_for('admin_downtimes_correction'))
    
    if request.form.get('start_time') and request.form.get('start_time').strip():
        try:
            downtime.start_time = datetime.strptime(request.form.get('start_time'), '%Y-%m-%dT%H:%M')
        except:
            pass
    
    if request.form.get('end_time') and request.form.get('end_time').strip():
        try:
            downtime.end_time = datetime.strptime(request.form.get('end_time'), '%Y-%m-%dT%H:%M')
        except:
            pass
    
    if request.form.get('reason_code'):
        downtime.reason_code = request.form.get('reason_code')
    
    if request.form.get('status'):
        new_status = request.form.get('status')
        downtime.status = new_status
        downtime.engineer_approved = (new_status == 'approved')
    
    if downtime.end_time and downtime.start_time and downtime.end_time <= downtime.start_time:
        flash('Ошибка: время окончания должно быть позже времени начала', 'danger')
        return redirect(url_for('admin_downtimes_correction'))
    
    db.session.commit()
    db.session.expire_all()
    
    log_audit(current_user.id, current_user.username, 'correct_downtime', 'downtime', 
              downtime.id, f'Корректировка простоя. Причина: {correction_reason}', request.remote_addr)
    
    flash('Простой скорректирован', 'success')
    return redirect(url_for('engineer_dashboard_page'))

# ---------- Управление пользователями (только админ) ----------

@app.route('/admin/users')
@login_required
@admin_required
def admin_users():
    users = User.query.all()
    ships = Ship.query.all()
    return render_template('admin/users.html', users=users, ships=ships)

@app.route('/admin/user/create', methods=['POST'])
@login_required
@admin_required
def admin_user_create():
    username = request.form.get('username')
    password = request.form.get('password')
    full_name = request.form.get('full_name')
    role = request.form.get('role')
    ship_id = request.form.get('ship_id') or None
    
    if User.query.filter_by(username=username).first():
        flash('Пользователь с таким именем уже существует', 'danger')
        return redirect(url_for('admin_users'))
    
    user = User(
        username=username,
        password_hash=generate_password_hash(password),
        full_name=full_name,
        role=role,
        ship_id=ship_id
    )
    db.session.add(user)
    db.session.commit()
    
    log_audit(current_user.id, current_user.username, 'create_user', 'user', 
              user.id, f'Создан пользователь {username}', request.remote_addr)
    
    flash('Пользователь создан', 'success')
    return redirect(url_for('admin_users'))

@app.route('/admin/user/<int:user_id>/edit', methods=['POST'])
@login_required
@admin_required
def admin_user_edit(user_id):
    user = User.query.get_or_404(user_id)
    user.full_name = request.form.get('full_name')
    user.role = request.form.get('role')
    user.ship_id = request.form.get('ship_id') or None
    db.session.commit()
    
    flash('Пользователь обновлён', 'success')
    return redirect(url_for('admin_users'))

@app.route('/admin/user/<int:user_id>/toggle', methods=['POST'])
@login_required
@admin_required
def admin_user_toggle(user_id):
    user = User.query.get_or_404(user_id)
    user.is_active = not user.is_active
    db.session.commit()
    
    flash(f'Пользователь {"активирован" if user.is_active else "деактивирован"}', 'success')
    return redirect(url_for('admin_users'))

@app.route('/admin/user/<int:user_id>/reset_password', methods=['POST'])
@login_required
@admin_required
def admin_user_reset_password(user_id):
    user = User.query.get_or_404(user_id)
    new_password = request.form.get('new_password', '123456')
    user.password_hash = generate_password_hash(new_password)
    db.session.commit()
    
    flash(f'Пароль сброшен на: {new_password}', 'success')
    return redirect(url_for('admin_users'))

@app.route('/admin/user/<int:user_id>/assign_ship', methods=['POST'])
@login_required
@admin_required
def admin_user_assign_ship(user_id):
    user = User.query.get_or_404(user_id)
    ship_id = request.form.get('ship_id')
    
    if ship_id:
        ship = Ship.query.get(ship_id)
        if ship:
            user.ship_id = ship_id
            flash(f'Капитану {user.full_name} назначено судно "{ship.name}"', 'success')
        else:
            flash('Судно не найдено', 'danger')
    else:
        user.ship_id = None
        flash(f'Назначение судна для {user.full_name} удалено', 'warning')
    
    db.session.commit()
    return redirect(url_for('admin_users'))

# ---------- Управление судами (инженер и админ) ----------

@app.route('/admin/ships')
@login_required
@engineer_required
def admin_ships():
    ships = Ship.query.all()
    return render_template('admin/ships.html', ships=ships)

@app.route('/admin/ship/create', methods=['POST'])
@login_required
@engineer_required
def admin_ship_create():
    nav_start = datetime.strptime(request.form.get('navigation_start'), '%Y-%m-%d')
    nav_end = datetime.strptime(request.form.get('navigation_end'), '%Y-%m-%d')
    nav_days = (nav_end - nav_start).days
    planned_hours = nav_days * 24
    
    ship = Ship(
        name=request.form.get('name'),
        reg_number=request.form.get('reg_number'),
        group=request.form.get('group'),
        navigation_start=nav_start,
        navigation_end=nav_end,
        planned_downtime_hours=planned_hours,
        is_active=True
    )
    db.session.add(ship)
    db.session.commit()
    
    log_audit(current_user.id, current_user.username, 'create_ship', 'ship', 
              ship.id, f'Создано судно {ship.name}', request.remote_addr)
    
    flash('Судно добавлено. Заполните его характеристики.', 'success')
    return redirect(url_for('admin_ship_characteristics', ship_id=ship.id))

@app.route('/admin/ship/<int:ship_id>/edit', methods=['POST'])
@login_required
@engineer_required
def admin_ship_edit(ship_id):
    ship = Ship.query.get_or_404(ship_id)
    
    nav_start = datetime.strptime(request.form.get('navigation_start'), '%Y-%m-%d')
    nav_end = datetime.strptime(request.form.get('navigation_end'), '%Y-%m-%d')
    nav_days = (nav_end - nav_start).days
    
    ship.name = request.form.get('name')
    ship.reg_number = request.form.get('reg_number')
    ship.group = request.form.get('group')
    ship.navigation_start = nav_start
    ship.navigation_end = nav_end
    ship.planned_downtime_hours = nav_days * 24
    
    db.session.commit()
    
    flash('Судно обновлено', 'success')
    return redirect(url_for('admin_ships'))

@app.route('/admin/ship/<int:ship_id>/characteristics', methods=['GET', 'POST'])
@login_required
@engineer_required
def admin_ship_characteristics(ship_id):
    ship = Ship.query.get_or_404(ship_id)
    values = {key: getattr(ship, key) or '' for key, _, _ in SHIP_FIELDS}

    if request.method == 'POST':
        values = {key: (request.form.get(key) or '').strip() for key, _, _ in SHIP_FIELDS}
        errors = []
        for key, label, _ in SHIP_FIELDS:
            max_len = Ship.__table__.c[key].type.length
            if len(values[key]) > max_len:
                errors.append(f'Поле «{label}» не должно быть длиннее {max_len} символов')
        if values['core'] and values['core'] not in CORE_CHOICES:
            errors.append('Некорректное значение поля «Рабочее ядро»')

        if not errors:
            for key, _, _ in SHIP_FIELDS:
                setattr(ship, key, values[key] or None)
            db.session.commit()
            log_audit(current_user.id, current_user.username, 'edit_ship_characteristics', 'ship',
                      ship.id, f'Изменены характеристики судна {ship.name}', request.remote_addr)
            flash('Характеристики судна сохранены', 'success')
            return redirect(url_for('admin_ships'))

        for error in errors:
            flash(error, 'danger')

    reference = find_reference(ship.name)
    return render_template('admin/ship_characteristics.html',
                           ship=ship,
                           fields=SHIP_FIELDS,
                           values=values,
                           core_choices=CORE_CHOICES,
                           reference_list=REFERENCE,
                           suggested=reference['name'] if reference else '')

@app.route('/admin/ship/<int:ship_id>/toggle', methods=['POST'])
@login_required
@engineer_required
def admin_ship_toggle(ship_id):
    ship = Ship.query.get_or_404(ship_id)
    ship.is_active = not ship.is_active
    db.session.commit()
    
    flash(f'Судно {"активировано" if ship.is_active else "деактивировано"}', 'success')
    return redirect(url_for('admin_ships'))

# ---------- Управление графиком ремонтов (инженер и админ) ----------

@app.route('/admin/maintenance')
@login_required
@engineer_required
def admin_maintenance():
    ships = Ship.query.filter_by(is_active=True).all()
    maintenance_plans = PlannedMaintenance.query.all()
    return render_template('admin/maintenance.html', 
                         ships=ships, 
                         maintenance_plans=maintenance_plans,
                         now=datetime.now())

@app.route('/admin/maintenance/create', methods=['POST'])
@login_required
@engineer_required
def admin_maintenance_create():
    ship_id = request.form.get('ship_id')
    year = request.form.get('year')
    planned_hours = float(request.form.get('planned_hours') or 0)
    
    existing = PlannedMaintenance.query.filter_by(ship_id=ship_id, year=year).first()
    if existing:
        existing.planned_hours = planned_hours
    else:
        plan = PlannedMaintenance(
            ship_id=ship_id,
            year=int(year),
            planned_hours=planned_hours
        )
        db.session.add(plan)
    
    # Обновляем плановое время судна
    ship = Ship.query.get(ship_id)
    if ship and ship.navigation_start and ship.navigation_end:
        nav_days = (ship.navigation_end - ship.navigation_start).days
        nav_hours = nav_days * 24
        ship.planned_downtime_hours = nav_hours - planned_hours
        if ship.planned_downtime_hours < 0:
            ship.planned_downtime_hours = 0
    
    db.session.commit()
    db.session.expire_all()
    
    flash('График ремонтов обновлён', 'success')
    return redirect(url_for('admin_maintenance'))

@app.route('/admin/maintenance/<int:plan_id>/delete', methods=['POST'])
@login_required
@engineer_required
def admin_maintenance_delete(plan_id):
    plan = PlannedMaintenance.query.get_or_404(plan_id)
    ship_id = plan.ship_id
    year = plan.year
    
    db.session.delete(plan)
    
    # Пересчитываем плановое время судна
    ship = Ship.query.get(ship_id)
    if ship and ship.navigation_start and ship.navigation_end:
        nav_days = (ship.navigation_end - ship.navigation_start).days
        nav_hours = nav_days * 24
        
        remaining_repairs = db.session.query(db.func.sum(PlannedMaintenance.planned_hours)).filter(
            PlannedMaintenance.ship_id == ship_id,
            PlannedMaintenance.year == year
        ).scalar() or 0
        
        ship.planned_downtime_hours = nav_hours - remaining_repairs
        if ship.planned_downtime_hours < 0:
            ship.planned_downtime_hours = 0
    
    db.session.commit()
    db.session.expire_all()
    
    flash('Запись удалена', 'success')
    return redirect(url_for('admin_maintenance'))

# ---------- Логи аудита (только админ) ----------

@app.route('/admin/logs')
@login_required
@admin_required
def admin_logs():
    user_filter = request.args.get('user_id', '')
    action_filter = request.args.get('action', '')
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    
    query = AuditLog.query
    
    if user_filter:
        query = query.filter_by(user_id=int(user_filter))
    if action_filter:
        query = query.filter(AuditLog.action.like(f'%{action_filter}%'))
    if date_from:
        query = query.filter(AuditLog.created_at >= datetime.strptime(date_from, '%Y-%m-%d'))
    if date_to:
        query = query.filter(AuditLog.created_at <= datetime.strptime(date_to, '%Y-%m-%d') + timedelta(days=1))
    
    logs = query.order_by(AuditLog.created_at.desc()).limit(500).all()
    users = User.query.all()
    actions = db.session.query(AuditLog.action).distinct().all()
    
    return render_template('admin/logs.html', logs=logs, users=users, actions=actions)

# ==================== API ДЛЯ JAVASCRIPT ====================

@app.route('/api/kpi/refresh')
@login_required
@engineer_required
def api_kpi_refresh():
    db.session.expire_all()
    kpi_data = KPICalculator.calculate_kpi_group_a()
    return jsonify(kpi_data)

@app.route('/api/downtimes/<int:downtime_id>')
@login_required
def api_downtime_detail(downtime_id):
    downtime = Downtime.query.get_or_404(downtime_id)
    
    return jsonify({
        'id': downtime.id,
        'ship_name': downtime.ship.name if downtime.ship else '',
        'start_time': downtime.start_time.isoformat(),
        'end_time': downtime.end_time.isoformat() if downtime.end_time else None,
        'duration_hours': calculate_duration_hours(downtime.start_time, downtime.end_time),
        'reason_code': downtime.reason_code,
        'reason_name': Config.DOWNTIME_REASONS.get(downtime.reason_code, ''),
        'description': downtime.description,
        'status': downtime.status,
        'files': [{'filename': f.filename, 'filepath': f.filepath} for f in downtime.files]
    })

@app.route('/api/ships/<int:ship_id>/info')
@login_required
def api_ship_info(ship_id):
    ship = Ship.query.get_or_404(ship_id)
    can_edit = current_user.role in (Config.ROLE_ENGINEER, Config.ROLE_ADMIN)
    return jsonify({
        'ship_name': ship.name,
        'filled': has_ship_info(ship),
        'fields': get_ship_info(ship),
        'edit_url': url_for('admin_ship_characteristics', ship_id=ship.id) if can_edit else None
    })

@app.route('/api/downtimes/bulk-approve', methods=['POST'])
@login_required
@engineer_required
def api_bulk_approve():
    data = request.get_json()
    ids = data.get('ids', [])
    
    approved_count = 0
    for downtime_id in ids:
        downtime = Downtime.query.get(downtime_id)
        if downtime and downtime.status == 'captain_signed':
            downtime.status = 'approved'
            downtime.engineer_approved = True
            approved_count += 1
    
    db.session.commit()
    return jsonify({'success': True, 'count': approved_count})

# ==================== ЗАПУСК ====================

if __name__ == '__main__':
    print("\n" + "="*50)
    print("Сервер запущен!")
    print("Доступ по адресу: http://localhost:5000")
    print("Логин: admin")
    print("Пароль: admin123")
    print("="*50 + "\n")
    
    app.run(host='0.0.0.0', port=5000, debug=True)