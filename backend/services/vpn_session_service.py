"""
Сервис для работы с VPN сессиями.
"""
from typing import Optional, List
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from backend.models.vpn_session import VPNSession, VPNSessionStatus
from backend.models.user import User, UserStatus
from backend.services.user_service import get_user_by_id, get_user_settings


def get_vpn_session_by_id(db: Session, session_id: str) -> Optional[VPNSession]:
    """Получить VPN сессию по ID."""
    return db.query(VPNSession).filter(VPNSession.id == session_id).first()


def get_active_vpn_session_for_user(db: Session, user_id: str) -> Optional[VPNSession]:
    """Получить активную VPN сессию для пользователя."""
    return db.query(VPNSession).filter(
        and_(
            VPNSession.user_id == user_id,
            VPNSession.status.in_([
                VPNSessionStatus.REQUESTED,
                VPNSessionStatus.CONNECTED,
                VPNSessionStatus.CONFIRMED,
                VPNSessionStatus.ACTIVE,
                VPNSessionStatus.REMINDER_SENT,
            ])
        )
    ).first()


def create_vpn_session(
    db: Session,
    user_id: str,
    reason: Optional[str] = None,
    duration_hours: int = 24,
    mikrotik_username: Optional[str] = None,
) -> VPNSession:
    """Создать новую VPN сессию."""
    # Проверяем, что пользователь существует и одобрен
    user = get_user_by_id(db, user_id)
    if not user:
        raise ValueError("User not found")
    
    if user.status not in [UserStatus.APPROVED, UserStatus.ACTIVE]:
        raise ValueError("User is not approved or active")
    
    # Проверяем, нет ли уже активной сессии
    existing_session = get_active_vpn_session_for_user(db, user_id)
    if existing_session:
        raise ValueError("User already has an active VPN session")
    
    # Генерируем имя пользователя MikroTik, если не указано
    if not mikrotik_username:
        # Формируем имя на основе telegram_id пользователя
        telegram_id = user.telegram_id if hasattr(user, 'telegram_id') and user.telegram_id else None
        if telegram_id:
            mikrotik_username = f"user_{telegram_id}"
        else:
            mikrotik_username = f"user_{user_id[:8]}"
    
    # Создаем новую сессию
    now = datetime.utcnow()
    vpn_session = VPNSession(
        user_id=user_id,
        mikrotik_username=mikrotik_username,
        status=VPNSessionStatus.REQUESTED,
        expires_at=now + timedelta(hours=duration_hours),
    )
    db.add(vpn_session)
    db.commit()
    db.refresh(vpn_session)
    
    return vpn_session


def update_vpn_session_status(
    db: Session,
    session_id: str,
    new_status: VPNSessionStatus,
    firewall_rule_id: Optional[str] = None,
) -> Optional[VPNSession]:
    """Обновить статус VPN сессии."""
    vpn_session = get_vpn_session_by_id(db, session_id)
    if not vpn_session:
        return None
    
    vpn_session.status = new_status
    
    # Обновляем временные метки в зависимости от статуса
    now = datetime.utcnow()
    if new_status == VPNSessionStatus.CONNECTED and not vpn_session.connected_at:
        vpn_session.connected_at = now
    elif new_status == VPNSessionStatus.CONFIRMED and not vpn_session.confirmed_at:
        vpn_session.confirmed_at = now
    elif new_status == VPNSessionStatus.REMINDER_SENT and not vpn_session.reminder_sent_at:
        vpn_session.reminder_sent_at = now
    
    if firewall_rule_id:
        vpn_session.firewall_rule_id = firewall_rule_id
    
    db.commit()
    db.refresh(vpn_session)
    return vpn_session


def mark_session_as_connected(
    db: Session,
    session_id: str,
) -> Optional[VPNSession]:
    """Отметить сессию как подключенную."""
    return update_vpn_session_status(db, session_id, VPNSessionStatus.CONNECTED)


def mark_session_as_confirmed(
    db: Session,
    session_id: str,
    firewall_rule_id: Optional[str] = None,
) -> Optional[VPNSession]:
    """Отметить сессию как подтвержденную и активную."""
    session = update_vpn_session_status(
        db, session_id, VPNSessionStatus.CONFIRMED, firewall_rule_id
    )
    if session:
        # Сразу делаем активной
        session = update_vpn_session_status(db, session_id, VPNSessionStatus.ACTIVE)
        # Устанавливаем время истечения на основе настроек пользователя
        user_settings = get_user_settings(db, session.user_id)
        reminder_hours = user_settings.reminder_interval_hours if user_settings else 6
        session.expires_at = datetime.utcnow() + timedelta(hours=reminder_hours)
        db.commit()
        db.refresh(session)
    return session


def mark_session_reminder_sent(
    db: Session,
    session_id: str,
) -> Optional[VPNSession]:
    """Отметить, что напоминание отправлено."""
    session = update_vpn_session_status(db, session_id, VPNSessionStatus.REMINDER_SENT)
    if session:
        # Обновляем время истечения
        user_settings = get_user_settings(db, session.user_id)
        reminder_hours = user_settings.reminder_interval_hours if user_settings else 6
        session.expires_at = datetime.utcnow() + timedelta(hours=reminder_hours)
        db.commit()
        db.refresh(session)
    return session


def disconnect_vpn_session(
    db: Session,
    session_id: str,
    user_id: Optional[str] = None,
) -> Optional[VPNSession]:
    """Отключить VPN сессию."""
    vpn_session = get_vpn_session_by_id(db, session_id)
    if not vpn_session:
        return None
    
    # Проверяем права доступа, если указан user_id
    if user_id and vpn_session.user_id != user_id:
        raise ValueError("User does not have permission to disconnect this session")
    
    vpn_session.status = VPNSessionStatus.DISCONNECTED
    db.commit()
    db.refresh(vpn_session)
    return vpn_session


def expire_vpn_session(
    db: Session,
    session_id: str,
) -> Optional[VPNSession]:
    """Отметить VPN сессию как истекшую."""
    vpn_session = get_vpn_session_by_id(db, session_id)
    if not vpn_session:
        return None
    
    vpn_session.status = VPNSessionStatus.EXPIRED
    db.commit()
    db.refresh(vpn_session)
    return vpn_session


def mark_session_as_expired(
    db: Session,
    session_id: str,
) -> Optional[VPNSession]:
    """Отметить VPN сессию как истекшую (алиас для expire_vpn_session)."""
    return expire_vpn_session(db, session_id)


def get_sessions_by_status(
    db: Session,
    statuses: List[VPNSessionStatus],
) -> List[VPNSession]:
    """Получить сессии по списку статусов."""
    return db.query(VPNSession).filter(
        VPNSession.status.in_(statuses)
    ).all()


def get_vpn_sessions(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    status: Optional[VPNSessionStatus] = None,
    user_id: Optional[str] = None,
) -> List[VPNSession]:
    """Получить список VPN сессий с фильтрацией."""
    query = db.query(VPNSession)
    
    if status is not None:
        query = query.filter(VPNSession.status == status)
    
    if user_id is not None:
        query = query.filter(VPNSession.user_id == user_id)
    
    # Сортировка: сначала активные, потом по дате создания (новые первыми)
    query = query.order_by(
        VPNSession.status.in_([
            VPNSessionStatus.ACTIVE,
            VPNSessionStatus.CONFIRMED,
            VPNSessionStatus.CONNECTED,
        ]),
        VPNSession.created_at.desc()
    )
    
    return query.offset(skip).limit(limit).all()


def get_active_vpn_sessions(db: Session) -> List[VPNSession]:
    """Получить все активные VPN сессии."""
    return get_vpn_sessions(
        db=db,
        status=VPNSessionStatus.ACTIVE,
        limit=1000,  # Получить все активные
    )


def count_vpn_sessions(
    db: Session,
    status: Optional[VPNSessionStatus] = None,
    user_id: Optional[str] = None,
) -> int:
    """Получить количество VPN сессий."""
    query = db.query(VPNSession)
    
    if status is not None:
        query = query.filter(VPNSession.status == status)
    
    if user_id is not None:
        query = query.filter(VPNSession.user_id == user_id)
    
    return query.count()


def get_user_vpn_sessions(
    db: Session,
    user_id: str,
    skip: int = 0,
    limit: int = 100,
) -> List[VPNSession]:
    """Получить VPN сессии пользователя."""
    return get_vpn_sessions(db=db, user_id=user_id, skip=skip, limit=limit)


def get_user_active_sessions(
    db: Session,
    user_id: str,
) -> List[VPNSession]:
    """Получить активные VPN сессии пользователя."""
    return db.query(VPNSession).filter(
        and_(
            VPNSession.user_id == user_id,
            VPNSession.status.in_([
                VPNSessionStatus.REQUESTED,
                VPNSessionStatus.CONNECTED,
                VPNSessionStatus.CONFIRMED,
                VPNSessionStatus.ACTIVE,
                VPNSessionStatus.REMINDER_SENT,
            ])
        )
    ).all()


def extend_session(
    db: Session,
    session_id: str,
    hours: Optional[int] = None,
) -> Optional[VPNSession]:
    """Продлить VPN сессию."""
    vpn_session = get_vpn_session_by_id(db, session_id)
    if not vpn_session:
        return None
    
    if vpn_session.status not in [VPNSessionStatus.ACTIVE, VPNSessionStatus.REMINDER_SENT]:
        raise ValueError("Can only extend active sessions")
    
    # Используем указанное количество часов или настройки пользователя
    if hours is None:
        user_settings = get_user_settings(db, vpn_session.user_id)
        hours = user_settings.reminder_interval_hours if user_settings else 6
    
    vpn_session.expires_at = datetime.utcnow() + timedelta(hours=hours)
    vpn_session.status = VPNSessionStatus.ACTIVE  # Возвращаем в активное состояние
    vpn_session.reminder_sent_at = None  # Сбрасываем флаг напоминания
    
    db.commit()
    db.refresh(vpn_session)
    return vpn_session
