from app import app
from models import db, Downtime, Ship
from datetime import datetime
from kpi_calculator import KPICalculator
import warnings
warnings.filterwarnings('ignore')

with app.app_context():
    print("=" * 60)
    print("РАСШИРЕННАЯ ДИАГНОСТИКА")
    print("=" * 60)
    
    # 1. Информация о судне
    ship = Ship.query.get(1)
    print(f"\n1. Судно:")
    print(f"   Название: {ship.name}")
    print(f"   Группа: {ship.group}")
    print(f"   Активно: {ship.is_active}")
    print(f"   Навигация: {ship.navigation_start} - {ship.navigation_end}")
    
    # 2. Простой #1
    downtime = Downtime.query.get(1)
    print(f"\n2. Простой #1:")
    print(f"   Статус: {downtime.status}")
    print(f"   engineer_approved: {downtime.engineer_approved}")
    print(f"   Начало: {downtime.start_time}")
    print(f"   Окончание: {downtime.end_time}")
    
    if downtime.end_time and downtime.start_time:
        delta = downtime.end_time - downtime.start_time
        hours = delta.total_seconds() / 3600
        print(f"   Длительность: {hours:.4f} часов ({hours*60:.1f} минут)")
    
    # 3. Проверяем, попадает ли простой в фильтр get_downtime_structure
    current_year = datetime.now().year
    start_date = datetime(current_year, 1, 1)
    end_date = datetime.now()
    
    print(f"\n3. Период фильтрации:")
    print(f"   с {start_date.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"   по {end_date.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Проверка условий
    conditions = [
        ("status == 'approved'", downtime.status == 'approved'),
        ("engineer_approved == True", downtime.engineer_approved == True),
        ("start_time >= start_date", downtime.start_time >= start_date),
        ("end_time <= end_date", downtime.end_time <= end_date),
        ("end_time is not None", downtime.end_time is not None),
        ("start_time is not None", downtime.start_time is not None),
    ]
    
    print(f"\n4. Проверка условий фильтрации:")
    all_true = True
    for cond, result in conditions:
        status = "✅" if result else "❌"
        print(f"   {status} {cond}: {result}")
        if not result:
            all_true = False
    
    if all_true:
        print(f"\n   ✅ Все условия выполнены! Простой ДОЛЖЕН учитываться.")
    else:
        print(f"\n   ❌ Есть невыполненные условия! Простой НЕ учитывается.")
    
    # 5. Прямой SQL запрос
    from sqlalchemy import func
    
    result = db.session.query(
        func.sum(func.extract('epoch', Downtime.end_time - Downtime.start_time) / 3600)
    ).filter(
        Downtime.ship_id == 1,
        Downtime.status == 'approved',
        Downtime.engineer_approved == True,
        Downtime.start_time >= start_date,
        Downtime.end_time <= end_date,
        Downtime.end_time.isnot(None),
        Downtime.start_time.isnot(None)
    ).scalar()
    
    print(f"\n5. Прямой SQL запрос для судна ID 1:")
    print(f"   Результат: {result if result else 0} часов")
    
    # 6. Проверка через метод calculate_kpi_group_a для конкретного судна
    from kpi_calculator import KPICalculator
    
    unplanned = KPICalculator.get_unplanned_downtime_hours(ship, start_date, end_date)
    print(f"\n6. get_unplanned_downtime_hours(): {unplanned} часов")
    
    # 7. Полный расчет КПЭ
    kpi = KPICalculator.calculate_kpi_group_a(current_year)
    print(f"\n7. calculate_kpi_group_a():")
    print(f"   total_unplanned_hours: {kpi['total_unplanned_hours']} часов")
    print(f"   total_planned_hours: {kpi['total_planned_hours']} часов")
    print(f"   kg: {kpi['kg']}%")
    
    # 8. Проверка всех простоев в БД
    print(f"\n8. Все утвержденные простои в БД:")
    all_approved = Downtime.query.filter_by(status='approved', engineer_approved=True).all()
    for dt in all_approved:
        ship_name = Ship.query.get(dt.ship_id).name if dt.ship_id else 'Unknown'
        hours = (dt.end_time - dt.start_time).total_seconds() / 3600 if dt.end_time else 0
        print(f"   ID:{dt.id} | Судно: {ship_name} | Часы: {hours:.4f} | Статус: {dt.status}")