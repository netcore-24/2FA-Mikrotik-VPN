"""
Сервис для отправки уведомлений через Telegram бота.
"""
import logging
from typing import Optional
from telegram import Bot
from telegram.error import TelegramError
from config.settings import settings
from backend.database import SessionLocal
from backend.services.user_service import get_user_by_id
from telegram_bot.utils.i18n import get_translation

logger = logging.getLogger(__name__)

# Глобальный экземпляр бота (будет установлен при инициализации)
_telegram_bot: Optional[Bot] = None


def set_telegram_bot(bot: Bot):
    """Установить экземпляр Telegram бота для отправки уведомлений."""
    global _telegram_bot
    _telegram_bot = bot
    logger.info("Telegram bot установлен для отправки уведомлений")


async def send_message_to_user(
    user_id: str,
    message: str,
    parse_mode: Optional[str] = None,
    reply_markup=None,
) -> bool:
    """
    Отправить сообщение пользователю через Telegram.
    
    Args:
        user_id: ID пользователя в системе
        message: Текст сообщения
        parse_mode: Режим парсинга (HTML, Markdown и т.д.)
        reply_markup: Inline клавиатура (опционально)
    
    Returns:
        True если сообщение отправлено успешно, False в противном случае
    """
    if not _telegram_bot:
        logger.warning("Telegram bot не установлен, уведомление не отправлено")
        return False
    
    db = SessionLocal()
    try:
        user = get_user_by_id(db, user_id)
        if not user or not user.telegram_id:
            logger.warning(f"Пользователь {user_id} не найден или не имеет telegram_id")
            return False
        
        # Определяем язык пользователя (по умолчанию русский)
        # TODO: В будущем можно добавить получение языка из настроек пользователя
        language = 'ru'
        
        await _telegram_bot.send_message(
            chat_id=user.telegram_id,
            text=message,
            parse_mode=parse_mode,
            reply_markup=reply_markup,
        )
        logger.info(f"Уведомление отправлено пользователю {user_id} (telegram_id: {user.telegram_id}, язык: {language})")
        return True
    
    except TelegramError as e:
        logger.error(f"Ошибка Telegram при отправке уведомления пользователю {user_id}: {e}")
        return False
    except Exception as e:
        logger.error(f"Ошибка при отправке уведомления пользователю {user_id}: {e}", exc_info=True)
        return False
    finally:
        db.close()


async def notify_session_confirmed(session, language: str = None):
    """Отправить уведомление о подтверждении VPN сессии."""
    # Получаем user_id из сессии
    user_id = session.user_id if hasattr(session, 'user_id') else None
    if not user_id:
        logger.warning(f"Сессия {session.id} не имеет user_id")
        return False
    
    # Определяем язык (по умолчанию русский)
    if not language:
        language = 'ru'
    
    t = get_translation(language)
    
    message = t('notifications.session_confirmed', {
        'session_id': session.id[:8],
        'expires_at': session.expires_at.strftime('%Y-%m-%d %H:%M') if session.expires_at else 'N/A',
    })
    
    return await send_message_to_user(user_id, message)


async def notify_session_disconnected(session, language: str = None):
    """Отправить уведомление об отключении VPN сессии."""
    user_id = session.user_id if hasattr(session, 'user_id') else None
    if not user_id:
        logger.warning(f"Сессия {session.id} не имеет user_id")
        return False
    
    if not language:
        db = SessionLocal()
        try:
            from backend.services.user_setting_service import get_user_setting_value
            language = get_user_setting_value(db, user_id, 'language') or 'ru'
        except:
            language = 'ru'
        finally:
            db.close()
    
    t = get_translation(language)
    
    message = t('notifications.session_disconnected', {
        'session_id': session.id[:8],
    })
    
    return await send_message_to_user(user_id, message)


async def notify_session_expired(session, language: str = None):
    """Отправить уведомление об истечении VPN сессии."""
    user_id = session.user_id if hasattr(session, 'user_id') else None
    if not user_id:
        logger.warning(f"Сессия {session.id} не имеет user_id")
        return False
    
    if not language:
        db = SessionLocal()
        try:
            from backend.services.user_setting_service import get_user_setting_value
            language = get_user_setting_value(db, user_id, 'language') or 'ru'
        except:
            language = 'ru'
        finally:
            db.close()
    
    t = get_translation(language)
    
    message = t('notifications.session_expired', {
        'session_id': session.id[:8],
    })
    
    return await send_message_to_user(user_id, message)


async def notify_session_reminder(session, hours_remaining: int, language: str = None):
    """Отправить напоминание о VPN сессии."""
    user_id = session.user_id if hasattr(session, 'user_id') else None
    if not user_id:
        logger.warning(f"Сессия {session.id} не имеет user_id")
        return False
    
    if not language:
        db = SessionLocal()
        try:
            from backend.services.user_setting_service import get_user_setting_value
            language = get_user_setting_value(db, user_id, 'language') or 'ru'
        except:
            language = 'ru'
        finally:
            db.close()
    
    t = get_translation(language)
    
    message = t('notifications.session_reminder', {
        'session_id': session.id[:8],
        'hours': hours_remaining,
        'expires_at': session.expires_at.strftime('%Y-%m-%d %H:%M') if session.expires_at else 'N/A',
    })
    
    return await send_message_to_user(user_id, message)
