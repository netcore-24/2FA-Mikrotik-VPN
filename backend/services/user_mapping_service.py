"""
Сервис для работы с сопоставлениями пользователей Telegram и MikroTik.
"""
from typing import List, Tuple, Optional
from sqlalchemy.orm import Session
from backend.models.user_mapping import UserMapping
from backend.models.user import User
from backend.services.mikrotik_service import get_user_manager_users
import logging

logger = logging.getLogger(__name__)


def get_user_mappings(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    telegram_user_id: Optional[str] = None,
    mikrotik_username: Optional[str] = None,
) -> Tuple[List[UserMapping], int]:
    """Получить список сопоставлений пользователей."""
    query = db.query(UserMapping)
    
    if telegram_user_id:
        query = query.filter(UserMapping.telegram_user_id == telegram_user_id)
    if mikrotik_username:
        query = query.filter(UserMapping.mikrotik_username == mikrotik_username)
    
    total = query.count()
    items = query.order_by(UserMapping.created_at.desc()).offset(skip).limit(limit).all()
    
    # Дополняем данные из таблицы пользователей
    for mapping in items:
        user = db.query(User).filter(User.id == mapping.telegram_user_id).first()
        if user:
            mapping.telegram_user_full_name = user.full_name
            mapping.telegram_user_email = user.email
            mapping.telegram_user_phone = user.phone
    
    return items, total


def get_user_mapping_by_id(db: Session, mapping_id: str) -> Optional[UserMapping]:
    """Получить сопоставление по ID."""
    mapping = db.query(UserMapping).filter(UserMapping.id == mapping_id).first()
    if mapping:
        # Дополняем данные из таблицы пользователей
        user = db.query(User).filter(User.id == mapping.telegram_user_id).first()
        if user:
            mapping.telegram_user_full_name = user.full_name
            mapping.telegram_user_email = user.email
            mapping.telegram_user_phone = user.phone
    return mapping


def create_user_mapping(
    db: Session,
    telegram_user_id: str,
    mikrotik_username: str,
) -> UserMapping:
    """Создать сопоставление пользователя."""
    # Проверяем, не существует ли уже такое сопоставление
    existing = db.query(UserMapping).filter(
        UserMapping.telegram_user_id == telegram_user_id
    ).first()
    if existing:
        raise ValueError(f"User mapping already exists for Telegram user {telegram_user_id}")
    
    # Проверяем, не сопоставлен ли уже MikroTik пользователь
    existing_mikrotik = db.query(UserMapping).filter(
        UserMapping.mikrotik_username == mikrotik_username
    ).first()
    if existing_mikrotik:
        raise ValueError(f"MikroTik user {mikrotik_username} is already mapped")
    
    # Проверяем существование Telegram пользователя
    user = db.query(User).filter(User.id == telegram_user_id).first()
    if not user:
        raise ValueError(f"Telegram user {telegram_user_id} not found")
    
    # Создаем сопоставление
    mapping = UserMapping(
        telegram_user_id=telegram_user_id,
        mikrotik_username=mikrotik_username,
        is_active=True,
    )
    db.add(mapping)
    db.commit()
    db.refresh(mapping)
    
    # Дополняем данные из таблицы пользователей
    mapping.telegram_user_full_name = user.full_name
    mapping.telegram_user_email = user.email
    mapping.telegram_user_phone = user.phone
    
    return mapping


def delete_user_mapping(db: Session, mapping_id: str) -> bool:
    """Удалить сопоставление пользователя."""
    mapping = db.query(UserMapping).filter(UserMapping.id == mapping_id).first()
    if not mapping:
        return False
    
    db.delete(mapping)
    db.commit()
    return True


def auto_map_users(db: Session) -> int:
    """
    Автоматически сопоставить пользователей Telegram и MikroTik
    по email или телефону.
    """
    mapped_count = 0
    
    try:
        # Получаем пользователей из MikroTik User Manager
        mikrotik_users_response = get_user_manager_users(db)
        if not mikrotik_users_response or not mikrotik_users_response.get('users'):
            logger.warning("No MikroTik users found for auto-mapping")
            return 0
        
        mikrotik_users = mikrotik_users_response['users']
        
        # Получаем всех Telegram пользователей без сопоставлений
        telegram_users = db.query(User).filter(
            ~User.id.in_(
                db.query(UserMapping.telegram_user_id)
            )
        ).all()
        
        for tg_user in telegram_users:
            # Пытаемся найти совпадение по email
            if tg_user.email:
                for mt_user in mikrotik_users:
                    mt_email = mt_user.get('email', '')
                    if mt_email and tg_user.email.lower() == mt_email.lower():
                        # Создаем сопоставление
                        try:
                            create_user_mapping(
                                db,
                                telegram_user_id=tg_user.id,
                                mikrotik_username=mt_user['name'],
                            )
                            mapped_count += 1
                            logger.info(f"Auto-mapped user {tg_user.id} to {mt_user['name']} by email")
                            break
                        except ValueError as e:
                            logger.warning(f"Failed to auto-map user {tg_user.id}: {e}")
            
            # Если не нашли по email, пытаемся найти по телефону
            if tg_user.phone and not db.query(UserMapping).filter(
                UserMapping.telegram_user_id == tg_user.id
            ).first():
                for mt_user in mikrotik_users:
                    mt_phone = mt_user.get('phone', '')
                    if mt_phone and tg_user.phone == mt_phone:
                        # Создаем сопоставление
                        try:
                            create_user_mapping(
                                db,
                                telegram_user_id=tg_user.id,
                                mikrotik_username=mt_user['name'],
                            )
                            mapped_count += 1
                            logger.info(f"Auto-mapped user {tg_user.id} to {mt_user['name']} by phone")
                            break
                        except ValueError as e:
                            logger.warning(f"Failed to auto-map user {tg_user.id}: {e}")
    
    except Exception as e:
        logger.error(f"Error during auto-mapping: {e}")
    
    return mapped_count


def get_mikrotik_username_for_telegram_user(
    db: Session, telegram_user_id: str
) -> Optional[str]:
    """Получить MikroTik username для Telegram пользователя."""
    mapping = db.query(UserMapping).filter(
        UserMapping.telegram_user_id == telegram_user_id,
        UserMapping.is_active == True,
    ).first()
    return mapping.mikrotik_username if mapping else None


def get_telegram_user_for_mikrotik_username(
    db: Session, mikrotik_username: str
) -> Optional[str]:
    """Получить Telegram user ID для MikroTik username."""
    mapping = db.query(UserMapping).filter(
        UserMapping.mikrotik_username == mikrotik_username,
        UserMapping.is_active == True,
    ).first()
    return mapping.telegram_user_id if mapping else None
