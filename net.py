from app import app, db
from models import Downtime
from datetime import datetime

with app.app_context():
    dt = Downtime.query.get(1)
    # Ставим дату окончания на сегодня
    dt.end_time = datetime.now()
    dt.status = 'approved'
    dt.engineer_approved = True
    db.session.commit()
    print(f"✅ Исправлено! Конец: {dt.end_time}")
    print(f"✅ Длительность: {(dt.end_time - dt.start_time).total_seconds() / 3600:.2f} часов")