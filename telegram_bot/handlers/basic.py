"""
Базовые обработчики команд (start, help, status, cancel).
"""
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from sqlalchemy.orm import Session

from backend.database import SessionLocal
from telegram_bot.utils.i18n import translate
from telegram_bot.middleware.auth import check_user_registered, get_user_from_db

logger = logging.getLogger(__name__)


async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start."""
    user = update.effective_user
    user_id = user.id
    db = SessionLocal()
    
    try:
        # Проверяем, зарегистрирован ли пользователь
        db_user = get_user_from_db(db, user_id)
        
        if db_user:
            # Пользователь зарегистрирован
            welcome_text = translate("bot.start.welcome_registered", user_id)
            welcome_text += f"\n\n{translate('bot.start.user_info', user_id)}"
            welcome_text += f"\n{translate('bot.common.full_name', user_id)}: {db_user.full_name or 'N/A'}"
            welcome_text += f"\n{translate('bot.common.status', user_id)}: {db_user.status.value}"
            
            # Добавляем кнопки для зарегистрированного пользователя
            keyboard = [
                [
                    InlineKeyboardButton(
                        translate("bot.buttons.request_vpn", user_id),
                        callback_data="action:request_vpn"
                    ),
                ],
                [
                    InlineKeyboardButton(
                        translate("bot.buttons.my_sessions", user_id),
                        callback_data="action:my_sessions"
                    ),
                ],
                [
                    InlineKeyboardButton(
                        translate("bot.buttons.status", user_id),
                        callback_data="action:status"
                    ),
                ],
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                welcome_text,
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )
        else:
            # Пользователь не зарегистрирован
            welcome_text = translate("bot.start.welcome_new", user_id)
            welcome_text += f"\n\n{translate('bot.start.instructions', user_id)}"
            
            keyboard = [
                [
                    InlineKeyboardButton(
                        translate("bot.buttons.register", user_id),
                        callback_data="action:register"
                    ),
                ],
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                welcome_text,
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )
    except Exception as e:
        logger.error(f"Ошибка в start_handler: {e}", exc_info=True)
        await update.message.reply_text(
            translate("bot.errors.internal_error", user_id)
        )
    finally:
        db.close()


async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /help."""
    user_id = update.effective_user.id
    
    help_text = translate("bot.help.title", user_id)
    help_text += "\n\n"
    help_text += translate("bot.help.commands", user_id)
    
    # Проверяем, зарегистрирован ли пользователь
    db = SessionLocal()
    try:
        is_registered = check_user_registered(db, user_id)
        
        if is_registered:
            help_text += "\n\n"
            help_text += translate("bot.help.commands_registered", user_id)
        else:
            help_text += "\n\n"
            help_text += translate("bot.help.commands_unregistered", user_id)
    finally:
        db.close()
    
    await update.message.reply_text(help_text, parse_mode="Markdown")


async def status_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /status."""
    user_id = update.effective_user.id
    db = SessionLocal()
    
    try:
        # Проверяем регистрацию
        if not check_user_registered(db, user_id):
            await update.message.reply_text(
                translate("bot.errors.not_registered", user_id)
            )
            return
        
        # Получаем информацию о пользователе
        db_user = get_user_from_db(db, user_id)
        if not db_user:
            await update.message.reply_text(
                translate("bot.errors.user_not_found", user_id)
            )
            return
        
        # Формируем статус
        status_text = translate("bot.status.title", user_id)
        status_text += f"\n\n{translate('bot.common.full_name', user_id)}: {db_user.full_name}"
        status_text += f"\n{translate('bot.common.status', user_id)}: {db_user.status.value}"
        
        if db_user.telegram_username:
            status_text += f"\n{translate('bot.common.username', user_id)}: @{db_user.telegram_username}"
        
        # Получаем информацию о VPN сессиях
        from backend.services.vpn_session_service import get_user_active_sessions
        active_sessions = get_user_active_sessions(db, db_user.id)
        
        if active_sessions:
            status_text += f"\n\n{translate('bot.status.active_sessions', user_id)}: {len(active_sessions)}"
            for session in active_sessions[:3]:  # Показываем первые 3
                status_text += f"\n- {session.id[:8]}... ({session.status.value})"
        else:
            status_text += f"\n\n{translate('bot.status.no_active_sessions', user_id)}"
        
        await update.message.reply_text(status_text, parse_mode="Markdown")
        
    except Exception as e:
        logger.error(f"Ошибка в status_handler: {e}", exc_info=True)
        await update.message.reply_text(
            translate("bot.errors.internal_error", user_id)
        )
    finally:
        db.close()


async def cancel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /cancel для отмены текущей операции."""
    user_id = update.effective_user.id
    
    # Завершаем conversation
    context.user_data.clear()
    
    await update.message.reply_text(
        translate("bot.cancel.message", user_id)
    )
    
    return ConversationHandler.END
