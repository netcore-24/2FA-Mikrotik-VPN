"""
API endpoints для сопоставления пользователей Telegram и MikroTik.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from typing import Optional
from backend.database import get_db
from backend.api.dependencies import get_current_admin
from backend.api.i18n_dependencies import get_translate
from backend.api.schemas import (
    UserMappingResponse,
    UserMappingListResponse,
    UserMappingCreate,
)
from backend.services.user_mapping_service import (
    get_user_mappings,
    get_user_mapping_by_id,
    create_user_mapping,
    delete_user_mapping,
    auto_map_users,
)
from backend.models.admin import Admin

router = APIRouter(prefix="/user-mappings", tags=["user-mappings"])


@router.get("", response_model=UserMappingListResponse)
async def get_user_mappings_endpoint(
    request: Request,
    skip: int = 0,
    limit: int = 100,
    telegram_user_id: Optional[str] = None,
    mikrotik_username: Optional[str] = None,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
    t=Depends(get_translate),
):
    """Получить список сопоставлений пользователей."""
    items, total = get_user_mappings(
        db, skip, limit, telegram_user_id, mikrotik_username
    )
    return UserMappingListResponse(items=items, total=total, skip=skip, limit=limit)


@router.get("/{mapping_id}", response_model=UserMappingResponse)
async def get_user_mapping_endpoint(
    mapping_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
    t=Depends(get_translate),
):
    """Получить сопоставление по ID."""
    mapping = get_user_mapping_by_id(db, mapping_id)
    if not mapping:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=t("error.not_found"),
        )
    return mapping


@router.post("", response_model=UserMappingResponse, status_code=status.HTTP_201_CREATED)
async def create_user_mapping_endpoint(
    mapping_data: UserMappingCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
    t=Depends(get_translate),
):
    """Создать сопоставление пользователя."""
    try:
        mapping = create_user_mapping(
            db,
            telegram_user_id=mapping_data.telegram_user_id,
            mikrotik_username=mapping_data.mikrotik_username,
        )
        return mapping
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.delete("/{mapping_id}")
async def delete_user_mapping_endpoint(
    mapping_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
    t=Depends(get_translate),
):
    """Удалить сопоставление пользователя."""
    success = delete_user_mapping(db, mapping_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=t("error.not_found"),
        )
    return {"message": t("success.deleted") or "Mapping deleted successfully"}


@router.post("/auto-map")
async def auto_map_users_endpoint(
    request: Request,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
    t=Depends(get_translate),
):
    """
    Автоматически сопоставить пользователей по email/телефону.
    """
    mapped_count = auto_map_users(db)
    return {
        "message": f"Successfully mapped {mapped_count} users",
        "mapped_count": mapped_count,
    }
