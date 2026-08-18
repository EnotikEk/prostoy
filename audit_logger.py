from flask import request
from models import AuditLog, db
from datetime import datetime

class AuditLogger:
    @staticmethod
    def log(user_id, username, action, target_type, target_id, details):
        try:
            log = AuditLog(
                user_id=user_id,
                username=username,
                action=action,
                target_type=target_type,
                target_id=target_id,
                details=details,
                ip_address=request.remote_addr or '0.0.0.0'
            )
            db.session.add(log)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            print(f"Audit log error: {e}")
    
    @staticmethod
    def get_logs(filters=None, limit=100):
        query = AuditLog.query.order_by(AuditLog.created_at.desc())
        if filters:
            if filters.get('user_id'):
                query = query.filter_by(user_id=filters['user_id'])
            if filters.get('action'):
                query = query.filter_by(action=filters['action'])
            if filters.get('date_from'):
                query = query.filter(AuditLog.created_at >= filters['date_from'])
            if filters.get('date_to'):
                query = query.filter(AuditLog.created_at <= filters['date_to'])
        return query.limit(limit).all()