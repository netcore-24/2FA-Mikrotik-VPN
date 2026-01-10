"""
API endpoints для управления пользователями.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request, Query
from sqlalchemy.orm import Session
from typing import Optional
from backend.database import get_db
from backend.api.dependencies import get_current_admin
from backend.api.i18n_dependencies import get_translate
from backend.api.schemas import (
    UserResponse,
    UserUpdate,
    UserListResponse,
)
from backend.services.user_service import (
    get_user_by_id,
    get_users,
    count_users,
    update_user,
    delete_user,
    change_user_status,
    get_user_settings,
    update_user_settings,
)
from backend.models.user import UserStatus
from backend.models.admin import Admin

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=UserListResponse)
async def list_users(
    request: Request,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    status_filter: Optional[str] = Query(None, alias="status"),
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
    t=Depends(get_translate),
):
    """
    Получить список пользователей с фильтрацией и поиском.
    """
    # Преобразуем строку статуса в enum
    user_status = None
    if status_filter:
        try:
            user_status = UserStatus(status_filter)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=t("validation.invalid_format"),
            )
    
    users = get_users(
        db=db,
        skip=skip,
        limit=limit,
        status=user_status,
        search=search,
    )
    total = count_users(db=db, status=user_status)
    
    # Преобразуем enum статуса в строку для каждого пользователя
    items = []
    for user in users:
        user_dict = {
            "id": user.id,
            "telegram_id": user.telegram_id,
            "full_name": user.full_name,
            "phone": user.phone,
            "email": user.email,
            "status": user.status.value,
            "created_at": user.created_at,
            "updated_at": user.updated_at,
            "approved_at": user.approved_at,
            "rejected_reason": user.rejected_reason,
        }
        items.append(UserResponse(**user_dict))
    
    return UserListResponse(
        items=items,
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
    t=Depends(get_translate),
):
    """
    Получить информацию о конкретном пользователе.
    """
    user = get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=t("user.not_found"),
        )
    
    # Преобразуем enum статуса в строку
    user_dict = {
        "id": user.id,
        "telegram_id": user.telegram_id,
        "full_name": user.full_name,
        "phone": user.phone,
        "email": user.email,
        "status": user.status.value,
        "created_at": user.created_at,
        "updated_at": user.updated_at,
        "approved_at": user.approved_at,
        "rejected_reason": user.rejected_reason,
    }
    return UserResponse(**user_dict)


@router.put("/{user_id}", response_model=UserResponse)
async def update_user_data(
    user_id: str,
    user_update: UserUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
    t=Depends(get_translate),
):
    """
    Обновить данные пользователя.
    """
    user = get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=t("user.not_found"),
        )
    
    # Преобразуем строку статуса в enum, если указана
    user_status = None
    if user_update.status:
        try:
            user_status = UserStatus(user_update.status)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=t("validation.invalid_format"),
            )
    
    updated_user = update_user(
        db=db,
        user_id=user_id,
        full_name=user_update.full_name,
        phone=user_update.phone,
        email=user_update.email,
        status=user_status,
    )
    
    if not updated_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=t("user.not_found"),
        )
    
    user_dict = {
        "id": updated_user.id,
        "telegram_id": updated_user.telegram_id,
        "full_name": updated_user.full_name,
        "phone": updated_user.phone,
        "email": updated_user.email,
        "status": updated_user.status.value,
        "created_at": updated_user.created_at,
        "updated_at": updated_user.updated_at,
        "approved_at": updated_user.approved_at,
        "rejected_reason": updated_user.rejected_reason,
    }
    return UserResponse(**user_dict)


@router.delete("/{user_id}")
async def delete_user_endpoint(
    user_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
    t=Depends(get_translate),
):
    """
    Удалить пользователя.
    """
    user = get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=t("user.not_found"),
        )
    
    success = delete_user(db, user_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=t("user.not_found"),
        )
    
    return {"message": t("user.deleted")}


@router.put("/{user_id}/status", response_model=UserResponse)
async def change_user_status_endpoint(
    user_id: str,
    new_status: str,
    request: Request,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
    t=Depends(get_translate),
):
    """
    Изменить статус пользователя.
    """
    try:
        status_enum = UserStatus(new_status)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=t("validation.invalid_format"),
        )
    
    updated_user = change_user_status(
        db=db,
        user_id=user_id,
        status=status_enum,
        admin_id=current_admin.id,
    )
    
    if not updated_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=t("user.not_found"),
        )
    
    user_dict = {
        "id": updated_user.id,
        "telegram_id": updated_user.telegram_id,
        "full_name": updated_user.full_name,
        "phone": updated_user.phone,
        "email": updated_user.email,
        "status": updated_user.status.value,
        "created_at": updated_user.created_at,
        "updated_at": updated_user.updated_at,
        "approved_at": updated_user.approved_at,
        "rejected_reason": updated_user.rejected_reason,
    }
    return UserResponse(**user_dict)


@router.get("/{user_id}/settings")
async def get_user_settings_endpoint(
    user_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
    t=Depends(get_translate),
):
    """
    Получить настройки пользователя.
    """
    user = get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=t("user.not_found"),
        )
    
    user_settings = get_user_settings(db, user_id)
    if not user_settings:
        # Возвращаем настройки по умолчанию
        return {
            "user_id": user_id,
            "firewall_rule_comment": None,
            "reminder_interval_hours": 6,
            "custom_notification_text": None,
        }
    
    return {
        "user_id": user_settings.user_id,
        "firewall_rule_comment": user_settings.firewall_rule_comment,
        "reminder_interval_hours": user_settings.reminder_interval_hours,
        "custom_notification_text": user_settings.custom_notification_text,
    }


@router.put("/{user_id}/settings")
async def update_user_settings_endpoint(
    user_id: str,
    firewall_rule_comment: Optional[str] = None,
    reminder_interval_hours: Optional[int] = None,
    custom_notification_text: Optional[str] = None,
    request: Request = None,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
    t=Depends(get_translate),
):
    """
    Обновить настройки пользователя.
    """
    user = get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=t("user.not_found"),
        )
    
    updated_settings = update_user_settings(
        db=db,
        user_id=user_id,
        firewall_rule_comment=firewall_rule_comment,
        reminder_interval_hours=reminder_interval_hours,
        custom_notification_text=custom_notification_text,
    )
    
    if not updated_settings:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=t("error.internal"),
        )
    
    return {
        "message": t("settings.updated"),
        "settings": {
            "user_id": updated_settings.user_id,
            "firewall_rule_comment": updated_settings.firewall_rule_comment,
            "reminder_interval_hours": updated_settings.reminder_interval_hours,
            "custom_notification_text": updated_settings.custom_notification_text,
        },
    }
