"""Настройки gunicorn. Запуск: gunicorn -c gunicorn.conf.py app:app"""
import os

# На сервере gunicorn слушает только локальный адрес — снаружи запросы принимает nginx.
# В Docker адрес переопределяется переменной GUNICORN_BIND=0.0.0.0:5000.
bind = os.environ.get('GUNICORN_BIND', '127.0.0.1:8000')

# Приложение загружается один раз в главном процессе (как --preload): таблицы и новые столбцы
# создаются при импорте app.py, и несколько процессов не должны делать это одновременно.
preload_app = True

# Число процессов и потоков. База — SQLite: записи всё равно идут по очереди,
# поэтому много процессов не ускоряет работу, а только повышает риск «database is locked».
workers = int(os.environ.get('GUNICORN_WORKERS', '2'))
threads = int(os.environ.get('GUNICORN_THREADS', '4'))
worker_class = 'gthread'

# Генерация отчётов Excel и импорт могут идти дольше стандартных 30 секунд
timeout = 120
graceful_timeout = 30
keepalive = 5

# Логи в stdout/stderr: на сервере их собирает journald (journalctl -u flot), в Docker — docker logs
accesslog = '-'
errorlog = '-'
loglevel = os.environ.get('GUNICORN_LOG_LEVEL', 'info')

# Доверять заголовкам X-Forwarded-* только от nginx на этой же машине
forwarded_allow_ips = '127.0.0.1'
