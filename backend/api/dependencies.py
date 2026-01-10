"""
Dependencies для FastAPI endpoints.
"""
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.services.auth_service import verify_token, get_admin_by_id
from backend.api.i18n_dependencies import get_translate
from backend.models.admin import Admin

security = HTTPBearer()


async def get_current_admin(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
    t=Depends(get_translate),
) -> Admin:
    """
    Dependency для получения текущего администратора из JWT токена.
    """
    token = credentials.credentials
    payload = verify_token(token, token_type="access")
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=t("auth.token.invalid"),
            headers={"WWW-Authenticate": "Bearer"},
        )
    admin_id: str = payload.get("sub")
    if admin_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=t("auth.token.invalid"),
        )
    admin = get_admin_by_id(db, admin_id)
    if admin is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=t("admin.not_found"),
        )
    if not admin.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=t("auth.login.inactive_account"),
        )
    return admin


async def get_current_super_admin(
    request: Request,
    current_admin: Admin = Depends(get_current_admin),
    t=Depends(get_translate),
) -> Admin:
    """
    Dependency для проверки, что текущий администратор - супер-администратор.
    """
    if not current_admin.is_super_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=t("auth.super_admin_required"),
        )
    return current_admin
