"""
Обработчики для работы с VPN сессиями.
"""
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from sqlalchemy.orm import Session

from backend.database import SessionLocal
from backend.services.vpn_session_service import (
    create_vpn_session,
    get_user_active_sessions,
    disconnect_vpn_session,
)
from backend.services.user_service import get_user_by_telegram_id
from telegram_bot.utils.i18n import translate
from telegram_bot.middleware.auth import check_user_registered, get_user_from_db

logger = logging.getLogger(__name__)

# Состояния conversation для запроса VPN
WAITING_REASON = "waiting_reason"


async def request_vpn_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /request_vpn и процесса запроса VPN."""
    user_id = update.effective_user.id
    db = SessionLocal()
    
    try:
        # Проверяем регистрацию
        if not check_user_registered(db, user_id):
            await update.message.reply_text(
                translate("bot.errors.not_registered", user_id)
            )
            return ConversationHandler.END
        
        # Получаем пользователя
        db_user = get_user_from_db(db, user_id)
        if not db_user:
            await update.message.reply_text(
                translate("bot.errors.user_not_found", user_id)
            )
            return ConversationHandler.END
        
        # Проверяем статус пользователя
        if db_user.status.value not in ["approved", "active"]:
            await update.message.reply_text(
                translate("bot.vpn.request.user_not_approved", user_id)
            )
            return ConversationHandler.END
        
        # Получаем текущее состояние conversation
        state = context.user_data.get("vpn_request_state")
        
        if state == WAITING_REASON:
            # Получаем причину запроса из сообщения
            reason = update.message.text.strip()
            
            if not reason or len(reason) < 5:
                await update.message.reply_text(
                    translate("bot.vpn.request.invalid_reason", user_id)
                )
                return WAITING_REASON
            
            # Создаем VPN сессию
            try:
                vpn_session = create_vpn_session(
                    db=db,
                    user_id=db_user.id,
                    reason=reason,
                    duration_hours=24,  # По умолчанию 24 часа
                )
                
                # Очищаем состояние
                context.user_data.clear()
                
                await update.message.reply_text(
                    translate("bot.vpn.request.success", user_id).format(
                        session_id=vpn_session.id[:8],
                        duration=24
                    )
                )
                
                # Показываем информацию о сессии
                session_info = translate("bot.vpn.request.session_info", user_id).format(
                    status=vpn_session.status.value,
                    created_at=vpn_session.created_at.strftime("%Y-%m-%d %H:%M:%S")
                )
                await update.message.reply_text(session_info)
                
                return ConversationHandler.END
                
            except Exception as e:
                logger.error(f"Ошибка при создании VPN сессии: {e}", exc_info=True)
                await update.message.reply_text(
                    translate("bot.errors.internal_error", user_id)
                )
                return ConversationHandler.END
        
        else:
            # Начало процесса запроса VPN
            # Проверяем, нет ли уже активных сессий
            active_sessions = get_user_active_sessions(db, db_user.id)
            
            if active_sessions:
                await update.message.reply_text(
                    translate("bot.vpn.request.has_active_sessions", user_id).format(
                        count=len(active_sessions)
                    )
                )
                
                # Показываем активные сессии
                for session in active_sessions[:3]:
                    session_text = translate("bot.vpn.request.active_session_info", user_id).format(
                        session_id=session.id[:8],
                        status=session.status.value,
                        created_at=session.created_at.strftime("%Y-%m-%d %H:%M:%S")
                    )
                    
                    # Кнопка для отключения
                    keyboard = [[
                        InlineKeyboardButton(
                            translate("bot.buttons.disconnect", user_id),
                            callback_data=f"disconnect_session:{session.id}"
                        )
                    ]]
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    
                    await update.message.reply_text(
                        session_text,
                        reply_markup=reply_markup
                    )
                
                return ConversationHandler.END
            
            # Запрашиваем причину
            await update.message.reply_text(
                translate("bot.vpn.request.welcome", user_id)
            )
            await update.message.reply_text(
                translate("bot.vpn.request.ask_reason", user_id)
            )
            
            # Устанавливаем состояние
            context.user_data["vpn_request_state"] = WAITING_REASON
            
            return WAITING_REASON
    
    except Exception as e:
        logger.error(f"Ошибка в request_vpn_handler: {e}", exc_info=True)
        await update.message.reply_text(
            translate("bot.errors.internal_error", user_id)
        )
        context.user_data.clear()
        return ConversationHandler.END
    finally:
        db.close()


async def my_sessions_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /my_sessions для просмотра активных сессий пользователя."""
    user_id = update.effective_user.id
    db = SessionLocal()
    
    try:
        # Проверяем регистрацию
        if not check_user_registered(db, user_id):
            await update.message.reply_text(
                translate("bot.errors.not_registered", user_id)
            )
            return
        
        # Получаем пользователя
        db_user = get_user_from_db(db, user_id)
        if not db_user:
            await update.message.reply_text(
                translate("bot.errors.user_not_found", user_id)
            )
            return
        
        # Получаем активные сессии
        active_sessions = get_user_active_sessions(db, db_user.id)
        
        if not active_sessions:
            await update.message.reply_text(
                translate("bot.vpn.sessions.no_active", user_id)
            )
            return
        
        # Показываем список сессий
        sessions_text = translate("bot.vpn.sessions.title", user_id).format(
            count=len(active_sessions)
        )
        sessions_text += "\n\n"
        
        for session in active_sessions:
            sessions_text += translate("bot.vpn.sessions.session_item", user_id).format(
                session_id=session.id[:8],
                status=session.status.value,
                created_at=session.created_at.strftime("%Y-%m-%d %H:%M:%S")
            )
            sessions_text += "\n"
        
        await update.message.reply_text(sessions_text)
        
        # Добавляем кнопки для управления сессиями
        for session in active_sessions[:5]:  # Показываем максимум 5 сессий
            keyboard = [[
                InlineKeyboardButton(
                    translate("bot.buttons.disconnect", user_id),
                    callback_data=f"disconnect_session:{session.id}"
                )
            ]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            session_info = translate("bot.vpn.sessions.session_details", user_id).format(
                session_id=session.id[:8],
                status=session.status.value
            )
            
            await update.message.reply_text(
                session_info,
                reply_markup=reply_markup
            )
        
    except Exception as e:
        logger.error(f"Ошибка в my_sessions_handler: {e}", exc_info=True)
        await update.message.reply_text(
            translate("bot.errors.internal_error", user_id)
        )
    finally:
        db.close()
