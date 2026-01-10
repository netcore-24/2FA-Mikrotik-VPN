"""
Сервис для отправки уведомлений через Telegram бота.
"""
import logging
from datetime import datetime
from typing import Optional
from telegram import Bot
from telegram.error import TelegramError
from config.settings import settings
from backend.database import SessionLocal
from backend.services.user_service import get_user_by_id
from backend.services.settings_service import get_setting_value
from telegram_bot.utils.i18n import translate
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

logger = logging.getLogger(__name__)

# Глобальный экземпляр бота (будет установлен при инициализации)
_telegram_bot: Optional[Bot] = None


def set_telegram_bot(bot: Bot):
    """Установить экземпляр Telegram бота для отправки уведомлений."""
    global _telegram_bot
    _telegram_bot = bot
    logger.info("Telegram bot установлен для отправки уведомлений")


class _SafeFormatDict(dict):
    """dict для format_map: неизвестные ключи оставляем как {key}."""

    def __missing__(self, key):
        return "{" + str(key) + "}"


def _render_template(template: str, ctx: dict) -> str:
    if not template:
        return ""
    try:
        return str(template).format_map(_SafeFormatDict(ctx))
    except Exception:
        # Если шаблон сломан фигурными скобками — не падаем
        return str(template)


def _format_dt(dt) -> str:
    try:
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return ""


def _get_user_ctx(db, user_id: str) -> dict:
    user = get_user_by_id(db, user_id)
    return {
        "full_name": (getattr(user, "full_name", None) or "").strip() or "-",
        "telegram_id": getattr(user, "telegram_id", None) or "",
    }


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
    # ВАЖНО: этот модуль используется и в backend-процессе (планировщик),
    # где `set_telegram_bot()` не вызывается. Поэтому делаем fallback
    # на прямую отправку через Bot(token).
    bot = _telegram_bot
    if not bot:
        if not settings.TELEGRAM_BOT_TOKEN:
            logger.warning("TELEGRAM_BOT_TOKEN не установлен, уведомление не отправлено")
            return False
        bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
    
    db = SessionLocal()
    try:
        user = get_user_by_id(db, user_id)
        if not user or not user.telegram_id:
            logger.warning(f"Пользователь {user_id} не найден или не имеет telegram_id")
            return False
        
        # Определяем язык пользователя (по умолчанию русский)
        # TODO: В будущем можно добавить получение языка из настроек пользователя
        language = 'ru'
        
        await bot.send_message(
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
    
    # Если задан шаблон в настройках — используем его
    db = SessionLocal()
    try:
        tmpl = get_setting_value(db, "telegram_template_session_confirmed", None) or ""
        ctx = {
            **_get_user_ctx(db, user_id),
            "mikrotik_username": getattr(session, "mikrotik_username", "") or "",
            "mikrotik_session_id": getattr(session, "mikrotik_session_id", None) or (session.id[:8] if getattr(session, "id", None) else ""),
            "expires_at": _format_dt(getattr(session, "expires_at", None)) or "N/A",
            "now": _format_dt(datetime.utcnow()),
        }
        message = _render_template(tmpl, ctx).strip()
    finally:
        db.close()

    if not message:
        message = translate(
            "bot.notifications.session_confirmed",
            language=language,
            session_id=session.id[:8],
            expires_at=session.expires_at.strftime("%Y-%m-%d %H:%M") if session.expires_at else "N/A",
        )
    
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
    
    db = SessionLocal()
    try:
        tmpl = get_setting_value(db, "telegram_template_session_disconnected", None) or ""
        ctx = {
            **_get_user_ctx(db, user_id),
            "mikrotik_username": getattr(session, "mikrotik_username", "") or "",
            "mikrotik_session_id": getattr(session, "mikrotik_session_id", None) or (session.id[:8] if getattr(session, "id", None) else ""),
            "expires_at": _format_dt(getattr(session, "expires_at", None)) or "N/A",
            "now": _format_dt(datetime.utcnow()),
        }
        message = _render_template(tmpl, ctx).strip()
    finally:
        db.close()

    if not message:
        message = translate(
            "bot.notifications.session_disconnected",
            language=language,
            session_id=session.id[:8],
        )
    
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
    
    db = SessionLocal()
    try:
        tmpl = get_setting_value(db, "telegram_template_session_expired", None) or ""
        ctx = {
            **_get_user_ctx(db, user_id),
            "mikrotik_username": getattr(session, "mikrotik_username", "") or "",
            "mikrotik_session_id": getattr(session, "mikrotik_session_id", None) or (session.id[:8] if getattr(session, "id", None) else ""),
            "expires_at": _format_dt(getattr(session, "expires_at", None)) or "N/A",
            "now": _format_dt(datetime.utcnow()),
        }
        message = _render_template(tmpl, ctx).strip()
    finally:
        db.close()

    if not message:
        message = translate(
            "bot.notifications.session_expired",
            language=language,
            session_id=session.id[:8],
        )
    
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
    
    db = SessionLocal()
    try:
        tmpl = get_setting_value(db, "telegram_template_session_reminder", None) or ""
        ctx = {
            **_get_user_ctx(db, user_id),
            "mikrotik_username": getattr(session, "mikrotik_username", "") or "",
            "mikrotik_session_id": getattr(session, "mikrotik_session_id", None) or (session.id[:8] if getattr(session, "id", None) else ""),
            "expires_at": _format_dt(getattr(session, "expires_at", None)) or "N/A",
            "hours_remaining": hours_remaining,
            "now": _format_dt(datetime.utcnow()),
        }
        message = _render_template(tmpl, ctx).strip()
    finally:
        db.close()

    if not message:
        message = translate(
            "bot.notifications.session_reminder",
            language=language,
            session_id=session.id[:8],
            hours=hours_remaining,
            expires_at=session.expires_at.strftime("%Y-%m-%d %H:%M") if session.expires_at else "N/A",
        )
    
    return await send_message_to_user(user_id, message)


async def notify_session_confirmation_required(session, language: str = None):
    """
    Отправить пользователю запрос подтверждения подключения.
    Если пользователь подтверждает — система включает firewall правило, закрепленное за пользователем.
    """
    user_id = session.user_id if hasattr(session, "user_id") else None
    if not user_id:
        return False
    if not language:
        language = "ru"

    db = SessionLocal()
    try:
        tmpl = get_setting_value(db, "telegram_template_confirmation_required", None) or ""
        ctx = {
            **_get_user_ctx(db, user_id),
            "mikrotik_username": getattr(session, "mikrotik_username", "") or "",
            "mikrotik_session_id": getattr(session, "mikrotik_session_id", None) or "",
            "expires_at": _format_dt(getattr(session, "expires_at", None)) or "N/A",
            "now": _format_dt(datetime.utcnow()),
        }
        text = _render_template(tmpl, ctx).strip()
    finally:
        db.close()

    if not text:
        mt_user = getattr(session, "mikrotik_username", "N/A")
        mt_sid = getattr(session, "mikrotik_session_id", None)
        sid_line = f"\nMikroTik session id: {mt_sid}" if mt_sid else ""
        text = (
            "❓ Обнаружено подключение к VPN.\n\n"
            f"Это вы подключились?\nMikroTik user: {mt_user}{sid_line}\n\n"
            "Подтвердите, чтобы открыть доступ (включить правило firewall)."
        )
    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ Да", callback_data=f"confirm_session:{session.id}:yes"),
                InlineKeyboardButton("❌ Нет", callback_data=f"confirm_session:{session.id}:no"),
            ]
        ]
    )
    return await send_message_to_user(user_id, text, reply_markup=keyboard)
