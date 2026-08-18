import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-me')
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'sqlite:///fleet.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', 'uploads')
    MAX_CONTENT_LENGTH = int(os.environ.get('MAX_CONTENT_LENGTH', 16 * 1024 * 1024))  # 16MB max
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'pdf', 'doc', 'docx', 'gif', 'bmp', 'txt'}
    
    # Роли пользователей
    ROLE_CAPTAIN = 'captain'
    ROLE_ENGINEER = 'engineer'
    ROLE_ADMIN = 'admin'
    
    # Коды причин простоя
    DOWNTIME_REASONS = {
        '01': 'Техническая неисправность',
        '02': 'Отсутствие запасных частей',
        '03': 'Погодные условия',
        '04': 'Ожидание грузовых операций',
        '05': 'Экипаж (недостаток/болезнь)',
        '06': 'Документальное оформление',
        '07': 'Прочие причины'
    }
    
    # Пороги КПЭ
    KPI_TARGET = 85
    KPI_ZERO_THRESHOLD = 80