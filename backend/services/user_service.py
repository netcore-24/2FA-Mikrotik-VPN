"""
Сервис для работы с пользователями.
"""
from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from backend.models.user import User, UserStatus
from backend.models.registration_request import RegistrationRequest, RegistrationRequestStatus
from backend.models.user_setting import UserSetting
import uuid


def get_user_by_id(db: Session, user_id: str) -> Optional[User]:
    """Получить пользователя по ID."""
    return db.query(User).filter(User.id == user_id).first()


def get_user_by_telegram_id(db: Session, telegram_id: int) -> Optional[User]:
    """Получить пользователя по Telegram ID."""
    return db.query(User).filter(User.telegram_id == telegram_id).first()


def create_user(
    db: Session,
    telegram_id: int,
    full_name: Optional[str] = None,
    phone: Optional[str] = None,
    email: Optional[str] = None,
) -> User:
    """Создать нового пользователя."""
    # Проверяем, не существует ли уже пользователь с таким Telegram ID
    existing_user = get_user_by_telegram_id(db, telegram_id)
    if existing_user:
        raise ValueError("User with this Telegram ID already exists")
    
    user = User(
        telegram_id=telegram_id,
        full_name=full_name,
        phone=phone,
        email=email,
        status=UserStatus.PENDING,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    
    # Создаем настройки пользователя по умолчанию
    user_setting = UserSetting(
        user_id=user.id,
        reminder_interval_hours=6,
    )
    db.add(user_setting)
    db.commit()
    
    return user


def update_user(
    db: Session,
    user_id: str,
    full_name: Optional[str] = None,
    phone: Optional[str] = None,
    email: Optional[str] = None,
    status: Optional[UserStatus] = None,
) -> Optional[User]:
    """Обновить данные пользователя."""
    user = get_user_by_id(db, user_id)
    if not user:
        return None
    
    if full_name is not None:
        user.full_name = full_name
    if phone is not None:
        user.phone = phone
    if email is not None:
        user.email = email
    if status is not None:
        user.status = status
    
    db.commit()
    db.refresh(user)
    return user


def delete_user(db: Session, user_id: str) -> bool:
    """Удалить пользователя."""
    user = get_user_by_id(db, user_id)
    if not user:
        return False
    
    db.delete(user)
    db.commit()
    return True


def change_user_status(
    db: Session,
    user_id: str,
    status: UserStatus,
    admin_id: Optional[str] = None,
    rejected_reason: Optional[str] = None,
) -> Optional[User]:
    """Изменить статус пользователя."""
    user = get_user_by_id(db, user_id)
    if not user:
        return None
    
    user.status = status
    
    if status == UserStatus.APPROVED:
        user.approved_by_id = admin_id
        from datetime import datetime
        user.approved_at = datetime.utcnow()
        user.rejected_reason = None
    elif status == UserStatus.REJECTED:
        user.rejected_reason = rejected_reason
        user.approved_by_id = None
        user.approved_at = None
    
    db.commit()
    db.refresh(user)
    return user


def get_users(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    status: Optional[UserStatus] = None,
    search: Optional[str] = None,
) -> List[User]:
    """Получить список пользователей с фильтрацией."""
    query = db.query(User)
    
    # Фильтр по статусу
    if status is not None:
        query = query.filter(User.status == status)
    
    # Поиск по имени, телефону, email
    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            or_(
                User.full_name.ilike(search_pattern),
                User.phone.ilike(search_pattern),
                User.email.ilike(search_pattern),
            )
        )
    
    # Сортировка по дате создания (новые первыми)
    query = query.order_by(User.created_at.desc())
    
    return query.offset(skip).limit(limit).all()


def count_users(db: Session, status: Optional[UserStatus] = None) -> int:
    """Получить количество пользователей."""
    query = db.query(User)
    if status is not None:
        query = query.filter(User.status == status)
    return query.count()


def get_user_settings(db: Session, user_id: str) -> Optional[UserSetting]:
    """Получить настройки пользователя."""
    return db.query(UserSetting).filter(UserSetting.user_id == user_id).first()


def update_user_settings(
    db: Session,
    user_id: str,
    firewall_rule_comment: Optional[str] = None,
    reminder_interval_hours: Optional[int] = None,
    custom_notification_text: Optional[str] = None,
) -> Optional[UserSetting]:
    """Обновить настройки пользователя."""
    user_setting = get_user_settings(db, user_id)
    if not user_setting:
        # Создаем настройки, если их нет
        user_setting = UserSetting(user_id=user_id)
        db.add(user_setting)
        db.commit()
        db.refresh(user_setting)
    
    if firewall_rule_comment is not None:
        user_setting.firewall_rule_comment = firewall_rule_comment
    if reminder_interval_hours is not None:
        user_setting.reminder_interval_hours = reminder_interval_hours
    if custom_notification_text is not None:
        user_setting.custom_notification_text = custom_notification_text
    
    db.commit()
    db.refresh(user_setting)
    return user_setting
