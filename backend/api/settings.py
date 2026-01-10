"""
API endpoints для управления системными настройками.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request, Query
from sqlalchemy.orm import Session
from typing import Optional, Any
from backend.database import get_db
from backend.api.dependencies import get_current_admin, get_current_super_admin
from backend.api.i18n_dependencies import get_translate
from backend.api.schemas import (
    SettingCreate,
    SettingUpdate,
    SettingResponse,
    SettingListResponse,
    SettingsDictResponse,
)
from backend.services.settings_service import (
    get_setting_by_key,
    get_all_settings,
    get_settings_by_category,
    set_setting,
    delete_setting,
    get_settings_dict,
    get_categories,
    get_setting_value,
)
from backend.models.admin import Admin

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("", response_model=SettingListResponse)
async def list_settings(
    request: Request,
    category: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
    t=Depends(get_translate),
):
    """
    Получить список всех настроек или настроек конкретной категории.
    """
    if category:
        settings_list = get_settings_by_category(db, category)
    else:
        settings_list = get_all_settings(db)
    
    categories_list = get_categories(db)
    
    # Формируем ответы, расшифровывая значения
    items = []
    for setting in settings_list:
        value = setting.value
        # Расшифровываем только если не супер-администратор (для безопасности)
        # В реальности лучше оставить как есть и расшифровывать только при необходимости
        items.append(SettingResponse(
            id=setting.id,
            key=setting.key,
            value=value,  # В реальном приложении можно расшифровать здесь
            category=setting.category,
            description=setting.description,
            is_encrypted=setting.is_encrypted,
            created_at=setting.created_at,
            updated_at=setting.updated_at,
        ))
    
    return SettingListResponse(
        items=items,
        total=len(items),
        categories=categories_list,
    )


@router.get("/dict", response_model=SettingsDictResponse)
async def get_settings_as_dict(
    request: Request,
    category: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
    t=Depends(get_translate),
):
    """
    Получить настройки в виде словаря (с автоматической расшифровкой и преобразованием типов).
    """
    settings_dict = get_settings_dict(db, category=category)
    return SettingsDictResponse(
        settings=settings_dict,
        category=category,
    )


@router.get("/categories")
async def get_settings_categories(
    request: Request,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
    t=Depends(get_translate),
):
    """
    Получить список всех категорий настроек.
    """
    categories = get_categories(db)
    return {"categories": categories}


@router.get("/{key}", response_model=SettingResponse)
async def get_setting(
    key: str,
    request: Request,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
    t=Depends(get_translate),
):
    """
    Получить конкретную настройку по ключу.
    """
    setting = get_setting_by_key(db, key)
    if not setting:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=t("settings.not_found"),
        )
    
    # Получаем значение (с расшифровкой, если нужно)
    value = get_setting_value(db, key)
    
    return SettingResponse(
        id=setting.id,
        key=setting.key,
        value=value,
        category=setting.category,
        description=setting.description,
        is_encrypted=setting.is_encrypted,
        created_at=setting.created_at,
        updated_at=setting.updated_at,
    )


@router.post("", response_model=SettingResponse, status_code=status.HTTP_201_CREATED)
async def create_setting(
    setting_data: SettingCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_super_admin),  # Только супер-администратор
    t=Depends(get_translate),
):
    """
    Создать новую настройку. Требуются права супер-администратора.
    """
    # Проверяем, не существует ли уже настройка с таким ключом
    existing_setting = get_setting_by_key(db, setting_data.key)
    if existing_setting:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=t("settings.not_found"),  # TODO: добавить "already_exists"
        )
    
    setting = set_setting(
        db=db,
        key=setting_data.key,
        value=setting_data.value,
        category=setting_data.category,
        description=setting_data.description,
        is_encrypted=setting_data.is_encrypted,
    )
    
    value = get_setting_value(db, setting.key)
    
    return SettingResponse(
        id=setting.id,
        key=setting.key,
        value=value,
        category=setting.category,
        description=setting.description,
        is_encrypted=setting.is_encrypted,
        created_at=setting.created_at,
        updated_at=setting.updated_at,
    )


@router.put("/{key}", response_model=SettingResponse)
async def update_setting(
    key: str,
    setting_update: SettingUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_super_admin),  # Только супер-администратор
    t=Depends(get_translate),
):
    """
    Обновить настройку. Требуются права супер-администратора.
    """
    setting = get_setting_by_key(db, key)
    if not setting:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=t("settings.not_found"),
        )
    
    updated_setting = set_setting(
        db=db,
        key=key,
        value=setting_update.value,
        category=setting_update.category or setting.category,
        description=setting_update.description if setting_update.description is not None else setting.description,
        is_encrypted=setting_update.is_encrypted if setting_update.is_encrypted is not None else setting.is_encrypted,
    )
    
    value = get_setting_value(db, updated_setting.key)
    
    return SettingResponse(
        id=updated_setting.id,
        key=updated_setting.key,
        value=value,
        category=updated_setting.category,
        description=updated_setting.description,
        is_encrypted=updated_setting.is_encrypted,
        created_at=updated_setting.created_at,
        updated_at=updated_setting.updated_at,
    )


@router.delete("/{key}")
async def delete_setting_endpoint(
    key: str,
    request: Request,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_super_admin),  # Только супер-администратор
    t=Depends(get_translate),
):
    """
    Удалить настройку. Требуются права супер-администратора.
    """
    setting = get_setting_by_key(db, key)
    if not setting:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=t("settings.not_found"),
        )
    
    success = delete_setting(db, key)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=t("settings.not_found"),
        )
    
    return {"message": t("settings.deleted")}
