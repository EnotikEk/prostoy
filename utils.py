from datetime import datetime, timedelta
import re
from flask import session

def validate_datetime_range(start_dt, end_dt):
    """Проверка корректности диапазона дат"""
    if not start_dt or not end_dt:
        return False, "Даты не могут быть пустыми"
    
    if end_dt <= start_dt:
        return False, "Дата окончания должна быть позже даты начала"
    
    if end_dt > datetime.now():
        return False, "Дата окончания не может быть в будущем"
    
    return True, "OK"

def calculate_duration_hours(start_dt, end_dt):
    """Расчёт длительности простоя в часах"""
    if not start_dt or not end_dt:
        return 0
    try:
        delta = end_dt - start_dt
        # Защита от отрицательной длительности
        if delta.total_seconds() < 0:
            return 0
        return round(delta.total_seconds() / 3600, 2)
    except Exception:
        return 0

def format_duration_hours(hours):
    """Форматирование длительности"""
    if hours is None or hours < 0:
        hours = 0
    if hours < 1:
        minutes = int(hours * 60)
        return f"{minutes} мин"
    elif hours < 24:
        return f"{hours:.1f} ч"
    else:
        days = int(hours // 24)
        remaining_hours = hours % 24
        return f"{days} д {remaining_hours:.1f} ч"

def validate_description(description):
    """Проверка описания (не менее 10 символов)"""
    if not description or len(description.strip()) < 10:
        return False, "Описание должно содержать не менее 10 символов"
    # Ограничиваем длину описания
    if len(description) > 500:
        return False, "Описание не должно превышать 500 символов"
    return True, "OK"

def get_quarter_from_date(date_obj):
    """Определение квартала по дате"""
    month = date_obj.month
    if month <= 3:
        return 1
    elif month <= 6:
        return 2
    elif month <= 9:
        return 3
    else:
        return 4

def get_current_quarter():
    """Текущий квартал"""
    return get_quarter_from_date(datetime.now())

def validate_file_upload(files, max_files=5):
    """Проверка загружаемых файлов"""
    if not files:
        return True, "OK"  # Файлы не обязательны
    
    if len(files) > max_files:
        return False, f"Максимальное количество файлов: {max_files}"
    
    return True, "OK"