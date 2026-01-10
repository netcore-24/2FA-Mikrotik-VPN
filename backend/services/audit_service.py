"""
Сервис для работы с журналом аудита.
"""
from typing import Optional, List
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc
from backend.models.audit_log import AuditLog
from backend.models.user import User
from backend.models.admin import Admin
import json


def create_audit_log(
    db: Session,
    action: str,
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    user_id: Optional[str] = None,
    admin_id: Optional[str] = None,
    details: Optional[dict] = None,
    ip_address: Optional[str] = None,
) -> AuditLog:
    """Создать запись в журнале аудита."""
    audit_log = AuditLog(
        user_id=user_id,
        admin_id=admin_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        details=json.dumps(details) if details else None,
        ip_address=ip_address,
    )
    db.add(audit_log)
    db.commit()
    db.refresh(audit_log)
    return audit_log


def get_audit_logs(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    user_id: Optional[str] = None,
    admin_id: Optional[str] = None,
    action: Optional[str] = None,
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
) -> List[AuditLog]:
    """Получить записи журнала аудита с фильтрацией."""
    query = db.query(AuditLog)
    
    if user_id:
        query = query.filter(AuditLog.user_id == user_id)
    if admin_id:
        query = query.filter(AuditLog.admin_id == admin_id)
    if action:
        query = query.filter(AuditLog.action == action)
    if entity_type:
        query = query.filter(AuditLog.entity_type == entity_type)
    if entity_id:
        query = query.filter(AuditLog.entity_id == entity_id)
    if start_date:
        query = query.filter(AuditLog.created_at >= start_date)
    if end_date:
        query = query.filter(AuditLog.created_at <= end_date)
    
    # Сортировка: новые записи первыми
    query = query.order_by(desc(AuditLog.created_at))
    
    return query.offset(skip).limit(limit).all()


def count_audit_logs(
    db: Session,
    user_id: Optional[str] = None,
    admin_id: Optional[str] = None,
    action: Optional[str] = None,
    entity_type: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
) -> int:
    """Получить количество записей в журнале аудита."""
    query = db.query(AuditLog)
    
    if user_id:
        query = query.filter(AuditLog.user_id == user_id)
    if admin_id:
        query = query.filter(AuditLog.admin_id == admin_id)
    if action:
        query = query.filter(AuditLog.action == action)
    if entity_type:
        query = query.filter(AuditLog.entity_type == entity_type)
    if start_date:
        query = query.filter(AuditLog.created_at >= start_date)
    if end_date:
        query = query.filter(AuditLog.created_at <= end_date)
    
    return query.count()


def get_audit_log_by_id(db: Session, log_id: str) -> Optional[AuditLog]:
    """Получить запись журнала аудита по ID."""
    return db.query(AuditLog).filter(AuditLog.id == log_id).first()


def get_user_audit_logs(
    db: Session,
    user_id: str,
    skip: int = 0,
    limit: int = 100,
) -> List[AuditLog]:
    """Получить журнал аудита для конкретного пользователя."""
    return get_audit_logs(db, skip=skip, limit=limit, user_id=user_id)


def get_admin_audit_logs(
    db: Session,
    admin_id: str,
    skip: int = 0,
    limit: int = 100,
) -> List[AuditLog]:
    """Получить журнал аудита для конкретного администратора."""
    return get_audit_logs(db, skip=skip, limit=limit, admin_id=admin_id)
