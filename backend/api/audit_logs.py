"""
API endpoints для работы с журналом аудита.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request, Query
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime
from backend.database import get_db
from backend.api.dependencies import get_current_admin
from backend.api.i18n_dependencies import get_translate
from backend.api.schemas import (
    AuditLogResponse,
    AuditLogListResponse,
)
from backend.services.audit_service import (
    get_audit_logs,
    get_audit_log_by_id,
    count_audit_logs,
    get_user_audit_logs,
    get_admin_audit_logs,
)
from backend.models.admin import Admin
import json

router = APIRouter(prefix="/audit-logs", tags=["audit-logs"])


@router.get("", response_model=AuditLogListResponse)
async def list_audit_logs(
    request: Request,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    user_id: Optional[str] = Query(None),
    admin_id: Optional[str] = Query(None),
    action: Optional[str] = Query(None),
    entity_type: Optional[str] = Query(None),
    entity_id: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None, description="ISO format: YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS"),
    end_date: Optional[str] = Query(None, description="ISO format: YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS"),
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
    t=Depends(get_translate),
):
    """
    Получить список записей журнала аудита с фильтрацией.
    """
    # Парсим даты, если указаны
    start_date_obj = None
    end_date_obj = None
    
    if start_date:
        try:
            start_date_obj = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
        except ValueError:
            try:
                start_date_obj = datetime.strptime(start_date, "%Y-%m-%d")
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=t("validation.invalid_format"),
                )
    
    if end_date:
        try:
            end_date_obj = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
        except ValueError:
            try:
                end_date_obj = datetime.strptime(end_date, "%Y-%m-%d")
                # Добавляем время конца дня
                end_date_obj = end_date_obj.replace(hour=23, minute=59, second=59)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=t("validation.invalid_format"),
                )
    
    logs = get_audit_logs(
        db=db,
        skip=skip,
        limit=limit,
        user_id=user_id,
        admin_id=admin_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        start_date=start_date_obj,
        end_date=end_date_obj,
    )
    total = count_audit_logs(
        db=db,
        user_id=user_id,
        admin_id=admin_id,
        action=action,
        entity_type=entity_type,
        start_date=start_date_obj,
        end_date=end_date_obj,
    )
    
    # Формируем ответы
    items = []
    for log in logs:
        details = None
        if log.details:
            try:
                details = json.loads(log.details)
            except (json.JSONDecodeError, TypeError):
                details = log.details
        
        items.append(AuditLogResponse(
            id=log.id,
            user_id=log.user_id,
            admin_id=log.admin_id,
            action=log.action,
            entity_type=log.entity_type,
            entity_id=log.entity_id,
            details=details,
            ip_address=log.ip_address,
            created_at=log.created_at,
        ))
    
    return AuditLogListResponse(
        items=items,
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get("/{log_id}", response_model=AuditLogResponse)
async def get_audit_log(
    log_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
    t=Depends(get_translate),
):
    """
    Получить конкретную запись журнала аудита по ID.
    """
    log = get_audit_log_by_id(db, log_id)
    if not log:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=t("error.not_found"),
        )
    
    details = None
    if log.details:
        try:
            details = json.loads(log.details)
        except (json.JSONDecodeError, TypeError):
            details = log.details
    
    return AuditLogResponse(
        id=log.id,
        user_id=log.user_id,
        admin_id=log.admin_id,
        action=log.action,
        entity_type=log.entity_type,
        entity_id=log.entity_id,
        details=details,
        ip_address=log.ip_address,
        created_at=log.created_at,
    )


@router.get("/user/{user_id}", response_model=AuditLogListResponse)
async def get_user_audit_logs_endpoint(
    user_id: str,
    request: Request,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
    t=Depends(get_translate),
):
    """
    Получить журнал аудита для конкретного пользователя.
    """
    logs = get_user_audit_logs(db, user_id, skip=skip, limit=limit)
    total = count_audit_logs(db, user_id=user_id)
    
    items = []
    for log in logs:
        details = None
        if log.details:
            try:
                details = json.loads(log.details)
            except (json.JSONDecodeError, TypeError):
                details = log.details
        
        items.append(AuditLogResponse(
            id=log.id,
            user_id=log.user_id,
            admin_id=log.admin_id,
            action=log.action,
            entity_type=log.entity_type,
            entity_id=log.entity_id,
            details=details,
            ip_address=log.ip_address,
            created_at=log.created_at,
        ))
    
    return AuditLogListResponse(
        items=items,
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get("/admin/{admin_id}", response_model=AuditLogListResponse)
async def get_admin_audit_logs_endpoint(
    admin_id: str,
    request: Request,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
    t=Depends(get_translate),
):
    """
    Получить журнал аудита для конкретного администратора.
    """
    logs = get_admin_audit_logs(db, admin_id, skip=skip, limit=limit)
    total = count_audit_logs(db, admin_id=admin_id)
    
    items = []
    for log in logs:
        details = None
        if log.details:
            try:
                details = json.loads(log.details)
            except (json.JSONDecodeError, TypeError):
                details = log.details
        
        items.append(AuditLogResponse(
            id=log.id,
            user_id=log.user_id,
            admin_id=log.admin_id,
            action=log.action,
            entity_type=log.entity_type,
            entity_id=log.entity_id,
            details=details,
            ip_address=log.ip_address,
            created_at=log.created_at,
        ))
    
    return AuditLogListResponse(
        items=items,
        total=total,
        skip=skip,
        limit=limit,
    )
