"""
Middleware для проверки аутентификации пользователей Telegram.
"""
from sqlalchemy.orm import Session
from backend.services.user_service import get_user_by_telegram_id
from backend.models.user import UserStatus


def check_user_registered(db: Session, telegram_id: int) -> bool:
    """
    Проверить, зарегистрирован ли пользователь и одобрен ли он.
    
    Args:
        db: Сессия базы данных
        telegram_id: ID пользователя в Telegram
    
    Returns:
        True, если пользователь зарегистрирован и одобрен/активен
    """
    user = get_user_by_telegram_id(db, telegram_id)
    if not user:
        return False
    
    # Проверяем статус пользователя
    return user.status in [UserStatus.APPROVED, UserStatus.ACTIVE]


def get_user_from_db(db: Session, telegram_id: int):
    """
    Получить пользователя из базы данных по Telegram ID.
    
    Args:
        db: Сессия базы данных
        telegram_id: ID пользователя в Telegram
    
    Returns:
        Объект User или None
    """
    return get_user_by_telegram_id(db, telegram_id)


def require_registration(func):
    """
    Декоратор для проверки регистрации пользователя перед выполнением функции.
    
    Usage:
        @require_registration
        async def some_handler(update, context, db, user):
            ...
    """
    async def wrapper(*args, **kwargs):
        # TODO: Реализовать декоратор, если потребуется
        return await func(*args, **kwargs)
    return wrapper
