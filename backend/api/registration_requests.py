"""
API endpoints для управления запросами на регистрацию.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request, Query
from sqlalchemy.orm import Session
from typing import Optional
from backend.database import get_db
from backend.api.dependencies import get_current_admin
from backend.api.i18n_dependencies import get_translate
from backend.api.schemas import (
    RegistrationRequestCreate,
    RegistrationRequestResponse,
    RegistrationRequestReject,
    RegistrationRequestListResponse,
    UserResponse,
)
from backend.services.registration_service import (
    get_registration_requests,
    get_registration_request_by_id,
    approve_registration_request,
    reject_registration_request,
    count_registration_requests,
    create_registration_request,
)
from backend.models.registration_request import RegistrationRequestStatus
from backend.models.admin import Admin

router = APIRouter(prefix="/registration-requests", tags=["registration-requests"])


@router.get("", response_model=RegistrationRequestListResponse)
async def list_registration_requests(
    request: Request,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    status_filter: Optional[str] = Query(None, alias="status"),
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
    t=Depends(get_translate),
):
    """
    Получить список запросов на регистрацию.
    """
    # Преобразуем строку статуса в enum
    request_status = None
    if status_filter:
        try:
            request_status = RegistrationRequestStatus(status_filter)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=t("validation.invalid_format"),
            )
    
    requests = get_registration_requests(
        db=db,
        skip=skip,
        limit=limit,
        status=request_status,
    )
    total = count_registration_requests(db=db, status=request_status)
    
    # Включаем информацию о пользователе
    items = []
    for req in requests:
        request_dict = {
            "id": req.id,
            "user_id": req.user_id,
            "status": req.status.value,
            "requested_at": req.requested_at,
            "reviewed_at": req.reviewed_at,
            "rejection_reason": req.rejection_reason,
            "user": UserResponse.model_validate(req.user) if req.user else None,
        }
        items.append(RegistrationRequestResponse(**request_dict))
    
    return RegistrationRequestListResponse(
        items=items,
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get("/{request_id}", response_model=RegistrationRequestResponse)
async def get_registration_request(
    request_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
    t=Depends(get_translate),
):
    """
    Получить информацию о конкретном запросе на регистрацию.
    """
    registration_request = get_registration_request_by_id(db, request_id)
    if not registration_request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=t("registration.request.not_found"),
        )
    
    request_dict = {
        "id": registration_request.id,
        "user_id": registration_request.user_id,
        "status": registration_request.status.value,
        "requested_at": registration_request.requested_at,
        "reviewed_at": registration_request.reviewed_at,
        "rejection_reason": registration_request.rejection_reason,
        "user": UserResponse.model_validate(registration_request.user) if registration_request.user else None,
    }
    return RegistrationRequestResponse(**request_dict)


@router.post("/{request_id}/approve", response_model=RegistrationRequestResponse)
async def approve_registration(
    request_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
    t=Depends(get_translate),
):
    """
    Одобрить запрос на регистрацию.
    """
    try:
        registration_request = approve_registration_request(
            db=db,
            request_id=request_id,
            admin_id=current_admin.id,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e) or t("registration.request.already_processed"),
        )
    
    if not registration_request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=t("registration.request.not_found"),
        )
    
    request_dict = {
        "id": registration_request.id,
        "user_id": registration_request.user_id,
        "status": registration_request.status.value,
        "requested_at": registration_request.requested_at,
        "reviewed_at": registration_request.reviewed_at,
        "rejection_reason": registration_request.rejection_reason,
        "user": UserResponse.model_validate(registration_request.user) if registration_request.user else None,
    }
    return RegistrationRequestResponse(**request_dict)


@router.post("/{request_id}/reject", response_model=RegistrationRequestResponse)
async def reject_registration(
    request_id: str,
    reject_data: RegistrationRequestReject,
    request: Request,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
    t=Depends(get_translate),
):
    """
    Отклонить запрос на регистрацию.
    """
    try:
        registration_request = reject_registration_request(
            db=db,
            request_id=request_id,
            admin_id=current_admin.id,
            rejection_reason=reject_data.rejection_reason,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e) or t("registration.request.already_processed"),
        )
    
    if not registration_request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=t("registration.request.not_found"),
        )
    
    request_dict = {
        "id": registration_request.id,
        "user_id": registration_request.user_id,
        "status": registration_request.status.value,
        "requested_at": registration_request.requested_at,
        "reviewed_at": registration_request.reviewed_at,
        "rejection_reason": registration_request.rejection_reason,
        "user": UserResponse.model_validate(registration_request.user) if registration_request.user else None,
    }
    return RegistrationRequestResponse(**request_dict)
