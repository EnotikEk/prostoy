import os
import hashlib
import time
from werkzeug.utils import secure_filename
from flask import current_app
from models import DowntimeFile, db
from config import Config

class FileUploader:
    
    @staticmethod
    def allowed_file(filename):
        return '.' in filename and \
               filename.rsplit('.', 1)[1].lower() in Config.ALLOWED_EXTENSIONS
    
    @staticmethod
    def save_files(files, downtime_id, upload_folder=None):
        if upload_folder is None:
            upload_folder = Config.UPLOAD_FOLDER
        
        if not os.path.exists(upload_folder):
            os.makedirs(upload_folder)
        
        saved_files = []
        
        for file in files:
            if file and file.filename and FileUploader.allowed_file(file.filename):
                # Получаем оригинальное имя и расширение
                original_filename = secure_filename(file.filename)
                ext = original_filename.rsplit('.', 1)[1].lower() if '.' in original_filename else ''
                
                # Генерируем уникальное имя для хранения
                unique_name = hashlib.md5(f"{downtime_id}{time.time()}{original_filename}".encode()).hexdigest()
                if ext:
                    stored_filename = f"{unique_name}.{ext}"
                else:
                    stored_filename = unique_name
                
                filepath = os.path.join(upload_folder, stored_filename)
                file.save(filepath)
                
                # Сохраняем запись в БД
                dt_file = DowntimeFile(
                    downtime_id=downtime_id,
                    filename=original_filename,  # Оригинальное имя для отображения
                    filepath=stored_filename     # Уникальное имя на диске
                )
                db.session.add(dt_file)
                saved_files.append(dt_file)
        
        db.session.commit()
        return saved_files
    
    @staticmethod
    def get_file_path(filename):
        return os.path.join(Config.UPLOAD_FOLDER, filename)
    
    @staticmethod
    def delete_file(file_id):
        dt_file = DowntimeFile.query.get(file_id)
        if dt_file:
            filepath = FileUploader.get_file_path(dt_file.filepath)
            if os.path.exists(filepath):
                os.remove(filepath)
            db.session.delete(dt_file)
            db.session.commit()
            return True
        return False