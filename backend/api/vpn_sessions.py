"""
API endpoints для управления VPN сессиями.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request, Query
from sqlalchemy.orm import Session
from typing import Optional
from backend.database import get_db
from backend.api.dependencies import get_current_admin
from backend.api.i18n_dependencies import get_translate
from backend.api.schemas import (
    VPNSessionCreate,
    VPNSessionResponse,
    VPNSessionListResponse,
    VPNSessionDisconnect,
    VPNSessionExtend,
    UserResponse,
)
from backend.services.vpn_session_service import (
    get_vpn_session_by_id,
    create_vpn_session,
    get_vpn_sessions,
    get_active_vpn_sessions,
    count_vpn_sessions,
    disconnect_vpn_session,
    expire_vpn_session,
    extend_session,
    mark_session_as_connected,
    mark_session_as_confirmed,
    mark_session_reminder_sent,
    get_user_vpn_sessions,
)
from backend.models.vpn_session import VPNSessionStatus
from backend.models.admin import Admin

router = APIRouter(prefix="/vpn-sessions", tags=["vpn-sessions"])


@router.get("", response_model=VPNSessionListResponse)
async def list_vpn_sessions(
    request: Request,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    status_filter: Optional[str] = Query(None, alias="status"),
    user_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
    t=Depends(get_translate),
):
    """
    Получить список VPN сессий с фильтрацией.
    """
    # Преобразуем строку статуса в enum
    session_status = None
    if status_filter:
        try:
            session_status = VPNSessionStatus(status_filter)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=t("validation.invalid_format"),
            )
    
    sessions = get_vpn_sessions(
        db=db,
        skip=skip,
        limit=limit,
        status=session_status,
        user_id=user_id,
    )
    total = count_vpn_sessions(db=db, status=session_status, user_id=user_id)
    
    # Формируем ответы с информацией о пользователях
    items = []
    for session in sessions:
        session_dict = {
            "id": session.id,
            "user_id": session.user_id,
            "mikrotik_username": session.mikrotik_username,
            "status": session.status.value,
            "connected_at": session.connected_at,
            "confirmed_at": session.confirmed_at,
            "expires_at": session.expires_at,
            "reminder_sent_at": session.reminder_sent_at,
            "firewall_rule_id": session.firewall_rule_id,
            "created_at": session.created_at,
            "updated_at": session.updated_at,
            "user": UserResponse(**{
                "id": session.user.id,
                "telegram_id": session.user.telegram_id,
                "full_name": session.user.full_name,
                "phone": session.user.phone,
                "email": session.user.email,
                "status": session.user.status.value,
                "created_at": session.user.created_at,
                "updated_at": session.user.updated_at,
                "approved_at": session.user.approved_at,
                "rejected_reason": session.user.rejected_reason,
            }) if session.user else None,
        }
        items.append(VPNSessionResponse(**session_dict))
    
    return VPNSessionListResponse(
        items=items,
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get("/active", response_model=VPNSessionListResponse)
async def get_active_vpn_sessions_endpoint(
    request: Request,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
    t=Depends(get_translate),
):
    """
    Получить все активные VPN сессии.
    """
    sessions = get_active_vpn_sessions(db=db)
    
    items = []
    for session in sessions:
        session_dict = {
            "id": session.id,
            "user_id": session.user_id,
            "mikrotik_username": session.mikrotik_username,
            "status": session.status.value,
            "connected_at": session.connected_at,
            "confirmed_at": session.confirmed_at,
            "expires_at": session.expires_at,
            "reminder_sent_at": session.reminder_sent_at,
            "firewall_rule_id": session.firewall_rule_id,
            "created_at": session.created_at,
            "updated_at": session.updated_at,
            "user": UserResponse(**{
                "id": session.user.id,
                "telegram_id": session.user.telegram_id,
                "full_name": session.user.full_name,
                "phone": session.user.phone,
                "email": session.user.email,
                "status": session.user.status.value,
                "created_at": session.user.created_at,
                "updated_at": session.user.updated_at,
                "approved_at": session.user.approved_at,
                "rejected_reason": session.user.rejected_reason,
            }) if session.user else None,
        }
        items.append(VPNSessionResponse(**session_dict))
    
    return VPNSessionListResponse(
        items=items,
        total=len(items),
        skip=0,
        limit=len(items),
    )


@router.get("/{session_id}", response_model=VPNSessionResponse)
async def get_vpn_session(
    session_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
    t=Depends(get_translate),
):
    """
    Получить информацию о конкретной VPN сессии.
    """
    vpn_session = get_vpn_session_by_id(db, session_id)
    if not vpn_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=t("vpn.session.not_found"),
        )
    
    session_dict = {
        "id": vpn_session.id,
        "user_id": vpn_session.user_id,
        "mikrotik_username": vpn_session.mikrotik_username,
        "status": vpn_session.status.value,
        "connected_at": vpn_session.connected_at,
        "confirmed_at": vpn_session.confirmed_at,
        "expires_at": vpn_session.expires_at,
        "reminder_sent_at": vpn_session.reminder_sent_at,
        "firewall_rule_id": vpn_session.firewall_rule_id,
        "created_at": vpn_session.created_at,
        "updated_at": vpn_session.updated_at,
        "user": UserResponse(**{
            "id": vpn_session.user.id,
            "telegram_id": vpn_session.user.telegram_id,
            "full_name": vpn_session.user.full_name,
            "phone": vpn_session.user.phone,
            "email": vpn_session.user.email,
            "status": vpn_session.user.status.value,
            "created_at": vpn_session.user.created_at,
            "updated_at": vpn_session.user.updated_at,
            "approved_at": vpn_session.user.approved_at,
            "rejected_reason": vpn_session.user.rejected_reason,
        }) if vpn_session.user else None,
    }
    return VPNSessionResponse(**session_dict)


@router.post("", response_model=VPNSessionResponse, status_code=status.HTTP_201_CREATED)
async def create_vpn_session_endpoint(
    session_data: VPNSessionCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
    t=Depends(get_translate),
):
    """
    Создать новую VPN сессию.
    """
    try:
        vpn_session = create_vpn_session(
            db=db,
            user_id=session_data.user_id,
            mikrotik_username=session_data.mikrotik_username,
        )
    except ValueError as e:
        error_message = str(e)
        if "already has an active" in error_message:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=t("vpn.session.already_active"),
            )
        elif "not found" in error_message:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=t("user.not_found"),
            )
        elif "not approved" in error_message:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=t("user.status_changed"),
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_message,
            )
    
    session_dict = {
        "id": vpn_session.id,
        "user_id": vpn_session.user_id,
        "mikrotik_username": vpn_session.mikrotik_username,
        "status": vpn_session.status.value,
        "connected_at": vpn_session.connected_at,
        "confirmed_at": vpn_session.confirmed_at,
        "expires_at": vpn_session.expires_at,
        "reminder_sent_at": vpn_session.reminder_sent_at,
        "firewall_rule_id": vpn_session.firewall_rule_id,
        "created_at": vpn_session.created_at,
        "updated_at": vpn_session.updated_at,
        "user": UserResponse(**{
            "id": vpn_session.user.id,
            "telegram_id": vpn_session.user.telegram_id,
            "full_name": vpn_session.user.full_name,
            "phone": vpn_session.user.phone,
            "email": vpn_session.user.email,
            "status": vpn_session.user.status.value,
            "created_at": vpn_session.user.created_at,
            "updated_at": vpn_session.user.updated_at,
            "approved_at": vpn_session.user.approved_at,
            "rejected_reason": vpn_session.user.rejected_reason,
        }) if vpn_session.user else None,
    }
    return VPNSessionResponse(**session_dict)


@router.post("/{session_id}/disconnect", response_model=VPNSessionResponse)
async def disconnect_vpn_session_endpoint(
    session_id: str,
    disconnect_data: VPNSessionDisconnect,
    request: Request,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
    t=Depends(get_translate),
):
    """
    Отключить VPN сессию.
    """
    vpn_session = disconnect_vpn_session(db, session_id)
    if not vpn_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=t("vpn.session.not_found"),
        )
    
    session_dict = {
        "id": vpn_session.id,
        "user_id": vpn_session.user_id,
        "mikrotik_username": vpn_session.mikrotik_username,
        "status": vpn_session.status.value,
        "connected_at": vpn_session.connected_at,
        "confirmed_at": vpn_session.confirmed_at,
        "expires_at": vpn_session.expires_at,
        "reminder_sent_at": vpn_session.reminder_sent_at,
        "firewall_rule_id": vpn_session.firewall_rule_id,
        "created_at": vpn_session.created_at,
        "updated_at": vpn_session.updated_at,
        "user": UserResponse(**{
            "id": vpn_session.user.id,
            "telegram_id": vpn_session.user.telegram_id,
            "full_name": vpn_session.user.full_name,
            "phone": vpn_session.user.phone,
            "email": vpn_session.user.email,
            "status": vpn_session.user.status.value,
            "created_at": vpn_session.user.created_at,
            "updated_at": vpn_session.user.updated_at,
            "approved_at": vpn_session.user.approved_at,
            "rejected_reason": vpn_session.user.rejected_reason,
        }) if vpn_session.user else None,
    }
    return VPNSessionResponse(**session_dict)


@router.post("/{session_id}/extend", response_model=VPNSessionResponse)
async def extend_vpn_session_endpoint(
    session_id: str,
    extend_data: VPNSessionExtend,
    request: Request,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
    t=Depends(get_translate),
):
    """
    Продлить VPN сессию.
    """
    try:
        vpn_session = extend_session(db, session_id, extend_data.hours)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    
    if not vpn_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=t("vpn.session.not_found"),
        )
    
    session_dict = {
        "id": vpn_session.id,
        "user_id": vpn_session.user_id,
        "mikrotik_username": vpn_session.mikrotik_username,
        "status": vpn_session.status.value,
        "connected_at": vpn_session.connected_at,
        "confirmed_at": vpn_session.confirmed_at,
        "expires_at": vpn_session.expires_at,
        "reminder_sent_at": vpn_session.reminder_sent_at,
        "firewall_rule_id": vpn_session.firewall_rule_id,
        "created_at": vpn_session.created_at,
        "updated_at": vpn_session.updated_at,
        "user": UserResponse(**{
            "id": vpn_session.user.id,
            "telegram_id": vpn_session.user.telegram_id,
            "full_name": vpn_session.user.full_name,
            "phone": vpn_session.user.phone,
            "email": vpn_session.user.email,
            "status": vpn_session.user.status.value,
            "created_at": vpn_session.user.created_at,
            "updated_at": vpn_session.user.updated_at,
            "approved_at": vpn_session.user.approved_at,
            "rejected_reason": vpn_session.user.rejected_reason,
        }) if vpn_session.user else None,
    }
    return VPNSessionResponse(**session_dict)
