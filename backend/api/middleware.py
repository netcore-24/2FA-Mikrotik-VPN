"""
Middleware для автоматического логирования действий в журнал аудита.
"""
from fastapi import Request, Depends
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.api.dependencies import get_current_admin
from backend.services.audit_service import create_audit_log
from backend.models.admin import Admin
from typing import Optional


async def log_action_to_audit(
    request: Request,
    action: str,
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    user_id: Optional[str] = None,
    details: Optional[dict] = None,
    db: Session = Depends(get_db),
    current_admin: Optional[Admin] = None,
) -> None:
    """
    Вспомогательная функция для логирования действия в журнал аудита.
    Можно использовать в endpoints для автоматического логирования.
    """
    # Получаем IP адрес из запроса
    ip_address = request.client.host if request.client else None
    # Пробуем получить из заголовков (если за прокси)
    if not ip_address:
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            ip_address = forwarded_for.split(",")[0].strip()
    
    admin_id = current_admin.id if current_admin else None
    
    create_audit_log(
        db=db,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        user_id=user_id,
        admin_id=admin_id,
        details=details,
        ip_address=ip_address,
    )
