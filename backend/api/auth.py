"""
API endpoints для аутентификации.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from datetime import timedelta
from backend.database import get_db
from backend.services.auth_service import (
    authenticate_admin,
    create_access_token,
    create_refresh_token,
    verify_token,
)
from backend.api.schemas import (
    LoginRequest,
    Token,
    RefreshTokenRequest,
    AdminResponse,
)
from backend.api.dependencies import get_current_admin
from backend.api.i18n_dependencies import get_translate
from backend.models.admin import Admin
from config.settings import settings

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=Token)
async def login(
    login_data: LoginRequest,
    request: Request,
    db: Session = Depends(get_db),
    t=Depends(get_translate),
):
    """
    Вход администратора в систему.
    """
    admin = authenticate_admin(db, login_data.username, login_data.password)
    if not admin:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=t("auth.login.invalid_credentials"),
        )
    
    # Создаем токены
    access_token_expires = timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": admin.id, "username": admin.username},
        expires_delta=access_token_expires,
    )
    refresh_token = create_refresh_token(
        data={"sub": admin.id, "username": admin.username},
    )
    
    return Token(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        admin=AdminResponse.model_validate(admin),
    )


@router.post("/refresh", response_model=Token)
async def refresh_token(
    refresh_data: RefreshTokenRequest,
    request: Request,
    db: Session = Depends(get_db),
    t=Depends(get_translate),
):
    """
    Обновление access токена с помощью refresh токена.
    """
    payload = verify_token(refresh_data.refresh_token, token_type="refresh")
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=t("auth.token.refresh_invalid"),
        )
    
    admin_id: str = payload.get("sub")
    username: str = payload.get("username")
    
    if admin_id is None or username is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=t("auth.token.refresh_invalid"),
        )
    
    # Проверяем, что администратор существует и активен
    from backend.services.auth_service import get_admin_by_id
    admin = get_admin_by_id(db, admin_id)
    if not admin or not admin.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=t("admin.not_found"),
        )
    
    # Создаем новые токены
    access_token_expires = timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": admin.id, "username": admin.username},
        expires_delta=access_token_expires,
    )
    new_refresh_token = create_refresh_token(
        data={"sub": admin.id, "username": admin.username},
    )
    
    return Token(
        access_token=access_token,
        refresh_token=new_refresh_token,
        token_type="bearer",
        admin=AdminResponse.model_validate(admin),
    )


@router.get("/me", response_model=AdminResponse)
async def get_current_user_info(
    current_admin: Admin = Depends(get_current_admin),
):
    """
    Получение информации о текущем администраторе.
    """
    return AdminResponse.model_validate(current_admin)


@router.post("/logout")
async def logout(
    request: Request,
    current_admin: Admin = Depends(get_current_admin),
    t=Depends(get_translate),
):
    """
    Выход из системы (на клиенте удаляется токен).
    В будущем здесь можно добавить черный список токенов.
    """
    return {"message": t("auth.logout.success")}
