"""
Сервис для работы с запросами на регистрацию.
"""
from typing import Optional, List
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import and_
from backend.models.user import User, UserStatus
from backend.models.registration_request import RegistrationRequest, RegistrationRequestStatus
from backend.services.user_service import create_user, change_user_status, get_user_by_telegram_id


def create_registration_request(
    db: Session,
    telegram_id: int,
    full_name: Optional[str] = None,
    phone: Optional[str] = None,
    email: Optional[str] = None,
) -> RegistrationRequest:
    """
    Создать запрос на регистрацию.
    Если пользователь уже существует, создается новый запрос на регистрацию.
    """
    # Проверяем, существует ли пользователь
    user = get_user_by_telegram_id(db, telegram_id)
    
    if not user:
        # Создаем нового пользователя со статусом PENDING
        user = create_user(
            db=db,
            telegram_id=telegram_id,
            full_name=full_name,
            phone=phone,
            email=email,
        )
    else:
        # Обновляем данные пользователя, если они изменились
        if full_name:
            user.full_name = full_name
        if phone:
            user.phone = phone
        if email:
            user.email = email
        db.commit()
    
    # Создаем запрос на регистрацию
    registration_request = RegistrationRequest(
        user_id=user.id,
        status=RegistrationRequestStatus.PENDING,
        requested_at=datetime.utcnow(),
    )
    db.add(registration_request)
    db.commit()
    db.refresh(registration_request)
    
    return registration_request


def get_registration_request_by_id(db: Session, request_id: str) -> Optional[RegistrationRequest]:
    """Получить запрос на регистрацию по ID."""
    return db.query(RegistrationRequest).filter(RegistrationRequest.id == request_id).first()


def get_registration_requests(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    status: Optional[RegistrationRequestStatus] = None,
) -> List[RegistrationRequest]:
    """Получить список запросов на регистрацию."""
    query = db.query(RegistrationRequest)
    
    if status is not None:
        query = query.filter(RegistrationRequest.status == status)
    
    # Сортировка: сначала pending, потом по дате
    query = query.order_by(
        RegistrationRequest.status == RegistrationRequestStatus.PENDING,
        RegistrationRequest.requested_at.desc()
    )
    
    return query.offset(skip).limit(limit).all()


def approve_registration_request(
    db: Session,
    request_id: str,
    admin_id: str,
) -> Optional[RegistrationRequest]:
    """Одобрить запрос на регистрацию."""
    registration_request = get_registration_request_by_id(db, request_id)
    if not registration_request:
        return None
    
    if registration_request.status != RegistrationRequestStatus.PENDING:
        raise ValueError("Registration request has already been processed")
    
    # Меняем статус пользователя на APPROVED
    user = change_user_status(
        db=db,
        user_id=registration_request.user_id,
        status=UserStatus.APPROVED,
        admin_id=admin_id,
    )
    
    if not user:
        return None
    
    # Обновляем запрос
    registration_request.status = RegistrationRequestStatus.APPROVED
    registration_request.reviewed_by_id = admin_id
    registration_request.reviewed_at = datetime.utcnow()
    
    db.commit()
    db.refresh(registration_request)
    
    return registration_request


def reject_registration_request(
    db: Session,
    request_id: str,
    admin_id: str,
    rejection_reason: str,
) -> Optional[RegistrationRequest]:
    """Отклонить запрос на регистрацию."""
    registration_request = get_registration_request_by_id(db, request_id)
    if not registration_request:
        return None
    
    if registration_request.status != RegistrationRequestStatus.PENDING:
        raise ValueError("Registration request has already been processed")
    
    # Меняем статус пользователя на REJECTED
    user = change_user_status(
        db=db,
        user_id=registration_request.user_id,
        status=UserStatus.REJECTED,
        admin_id=admin_id,
        rejected_reason=rejection_reason,
    )
    
    if not user:
        return None
    
    # Обновляем запрос
    registration_request.status = RegistrationRequestStatus.REJECTED
    registration_request.reviewed_by_id = admin_id
    registration_request.reviewed_at = datetime.utcnow()
    registration_request.rejection_reason = rejection_reason
    
    db.commit()
    db.refresh(registration_request)
    
    return registration_request


def count_registration_requests(db: Session, status: Optional[RegistrationRequestStatus] = None) -> int:
    """Получить количество запросов на регистрацию."""
    query = db.query(RegistrationRequest)
    if status is not None:
        query = query.filter(RegistrationRequest.status == status)
    return query.count()
