from models import Ship, Downtime, PlannedMaintenance, db
from datetime import datetime

class KPICalculator:
    
    @staticmethod
    def get_navigation_hours(ship, year):
        """Расчет длительности навигационного периода в часах"""
        if not ship.navigation_start or not ship.navigation_end:
            return 0.0
        
        nav_start = datetime(year, ship.navigation_start.month, ship.navigation_start.day)
        nav_end = datetime(year, ship.navigation_end.month, ship.navigation_end.day)
        
        if nav_end < nav_start:
            nav_end = datetime(year + 1, ship.navigation_end.month, ship.navigation_end.day)
        
        delta = nav_end - nav_start
        hours = delta.days * 24
        return max(hours, 0)
    
    @staticmethod
    def get_planned_repair_hours(ship, year):
        """Плановые часы ремонта из графика"""
        planned = PlannedMaintenance.query.filter_by(
            ship_id=ship.id, year=year
        ).first()
        if planned and planned.planned_hours > 0:
            return float(planned.planned_hours)
        return 0.0
    
    @staticmethod
    def get_planned_hours(ship, year):
        """Плановое время готовности = Навигация - Ремонты"""
        nav_hours = KPICalculator.get_navigation_hours(ship, year)
        repair_hours = KPICalculator.get_planned_repair_hours(ship, year)
        
        planned = nav_hours - repair_hours
        if planned <= 0:
            planned = 1.0
        return planned
    
    @staticmethod
    def get_unplanned_downtime_hours(ship, start_date, end_date):
        """Сумма внеплановых простоев судна за период"""
        downtimes = Downtime.query.filter(
            Downtime.ship_id == ship.id,
            Downtime.status == 'approved',
            Downtime.engineer_approved == True,
            Downtime.end_time.isnot(None),
            Downtime.start_time.isnot(None),
            Downtime.start_time >= start_date,
            Downtime.end_time <= end_date
        ).all()
        
        total_hours = 0.0
        for dt in downtimes:
            if dt.end_time and dt.start_time and dt.end_time > dt.start_time:
                delta = dt.end_time - dt.start_time
                hours = delta.total_seconds() / 3600
                if 0 < hours < 8760:
                    total_hours += hours
        
        return total_hours
    
    @staticmethod
    def calculate_kpi_group_a(year=None, quarter=None):
        """Расчёт КПЭ для группы А"""
        if year is None:
            year = datetime.now().year
        
        # Определяем период расчета
        if quarter:
            if quarter == 1:
                start_date = datetime(year, 1, 1)
                end_date = datetime(year, 3, 31, 23, 59, 59)
            elif quarter == 2:
                start_date = datetime(year, 4, 1)
                end_date = datetime(year, 6, 30, 23, 59, 59)
            elif quarter == 3:
                start_date = datetime(year, 7, 1)
                end_date = datetime(year, 9, 30, 23, 59, 59)
            elif quarter == 4:
                start_date = datetime(year, 10, 1)
                end_date = datetime(year, 12, 31, 23, 59, 59)
            else:
                start_date = datetime(year, 1, 1)
                end_date = datetime.now()
        else:
            start_date = datetime(year, 1, 1)
            end_date = datetime.now()
        
        ships_a = Ship.query.filter_by(group='A', is_active=True).all()
        
        if not ships_a:
            return {
                'total_planned_hours': 0.0,
                'total_unplanned_hours': 0.0,
                'kg': 100.0,
                'score': 100.0,
                'ships_data': [],
                'start_date': start_date,
                'end_date': end_date
            }
        
        total_planned = 0.0
        total_unplanned = 0.0
        ships_data = []
        
        for ship in ships_a:
            planned_hours = KPICalculator.get_planned_hours(ship, year)
            unplanned_hours = KPICalculator.get_unplanned_downtime_hours(ship, start_date, end_date)
            
            if unplanned_hours > planned_hours and planned_hours > 0:
                unplanned_hours = planned_hours
            
            total_planned += planned_hours
            total_unplanned += unplanned_hours
            
            if planned_hours > 0:
                kg_ship = ((planned_hours - unplanned_hours) / planned_hours) * 100
                kg_ship = max(0.0, min(100.0, kg_ship))
            else:
                kg_ship = 0.0
            
            ships_data.append({
                'ship_name': ship.name,
                'planned_hours': round(planned_hours, 2),
                'unplanned_hours': round(unplanned_hours, 2),
                'kg': round(kg_ship, 2)
            })
        
        if total_planned > 0:
            kg_total = ((total_planned - total_unplanned) / total_planned) * 100
            kg_total = max(0.0, min(100.0, kg_total))
        else:
            kg_total = 0.0
        
        # Оценка выполнения КПЭ №5
        if kg_total >= 85:
            score = 100.0
        elif kg_total < 80:
            score = 0.0
        else:
            score = ((kg_total - 80) / 5) * 100
        
        return {
            'total_planned_hours': round(total_planned, 2),
            'total_unplanned_hours': round(total_unplanned, 2),
            'kg': round(kg_total, 2),
            'score': round(score, 2),
            'ships_data': ships_data,
            'start_date': start_date,
            'end_date': end_date
        }
    
    @staticmethod
    def get_downtime_structure(ship_id=None, start_date=None, end_date=None):
        """Структура простоев по кодам причин"""
        from config import Config
        
        if start_date is None:
            start_date = datetime(datetime.now().year, 1, 1)
        if end_date is None:
            end_date = datetime.now()
        
        query = Downtime.query.filter(
            Downtime.status == 'approved',
            Downtime.engineer_approved == True,
            Downtime.end_time.isnot(None),
            Downtime.start_time.isnot(None),
            Downtime.start_time >= start_date,
            Downtime.end_time <= end_date
        )
        
        if ship_id:
            query = query.filter_by(ship_id=ship_id)
        
        downtimes = query.all()
        
        structure = {}
        for code, name in Config.DOWNTIME_REASONS.items():
            structure[code] = {
                'name': name,
                'hours': 0.0,
                'count': 0
            }
        
        total_hours = 0.0
        for dt in downtimes:
            if dt.reason_code and dt.reason_code in structure:
                if dt.end_time and dt.start_time and dt.end_time > dt.start_time:
                    delta = dt.end_time - dt.start_time
                    hours = delta.total_seconds() / 3600
                    if 0 < hours < 8760:
                        structure[dt.reason_code]['hours'] += hours
                        structure[dt.reason_code]['count'] += 1
                        total_hours += hours
        
        structure['_total_hours'] = total_hours
        structure['_start_date'] = start_date
        structure['_end_date'] = end_date
        
        return structure
    
    @staticmethod
    def clear_cache():
        """Полный сброс всех кэшей БД"""
        db.session.expire_all()
        db.session.flush()