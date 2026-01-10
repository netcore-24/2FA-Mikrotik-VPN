"""
Обработчики для регистрации пользователей.
"""
import logging
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
from sqlalchemy.orm import Session

from backend.database import SessionLocal
from backend.services.registration_service import create_registration_request
from backend.services.user_service import get_user_by_telegram_id
from telegram_bot.utils.i18n import translate
from telegram_bot.middleware.auth import check_user_registered

logger = logging.getLogger(__name__)

# Состояния conversation для регистрации
WAITING_FULL_NAME = "waiting_full_name"


async def register_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /register и процесса регистрации."""
    user = update.effective_user
    user_id = user.id
    db = SessionLocal()
    
    try:
        # Проверяем, не зарегистрирован ли уже пользователь
        if check_user_registered(db, user_id):
            await update.message.reply_text(
                translate("bot.register.already_registered", user_id)
            )
            return ConversationHandler.END
        
        # Получаем текущее состояние conversation
        state = context.user_data.get("registration_state")
        
        if state == WAITING_FULL_NAME:
            # Получаем полное имя из сообщения
            full_name = update.message.text.strip()
            
            if not full_name or len(full_name) < 2:
                await update.message.reply_text(
                    translate("bot.register.invalid_name", user_id)
                )
                return WAITING_FULL_NAME
            
            # Создаем запрос на регистрацию
            try:
                registration_request = create_registration_request(
                    db=db,
                    telegram_id=user_id,
                    telegram_username=user.username,
                    full_name=full_name,
                    additional_info={
                        "telegram_first_name": user.first_name,
                        "telegram_last_name": user.last_name,
                    },
                )
                
                # Очищаем состояние
                context.user_data.clear()
                
                await update.message.reply_text(
                    translate("bot.register.success", user_id).format(
                        request_id=registration_request.id[:8]
                    )
                )
                await update.message.reply_text(
                    translate("bot.register.waiting_approval", user_id)
                )
                
                return ConversationHandler.END
                
            except Exception as e:
                logger.error(f"Ошибка при создании запроса на регистрацию: {e}", exc_info=True)
                await update.message.reply_text(
                    translate("bot.errors.internal_error", user_id)
                )
                return ConversationHandler.END
        
        else:
            # Начало процесса регистрации
            await update.message.reply_text(
                translate("bot.register.welcome", user_id)
            )
            await update.message.reply_text(
                translate("bot.register.ask_full_name", user_id)
            )
            
            # Устанавливаем состояние
            context.user_data["registration_state"] = WAITING_FULL_NAME
            
            return WAITING_FULL_NAME
    
    except Exception as e:
        logger.error(f"Ошибка в register_handler: {e}", exc_info=True)
        await update.message.reply_text(
            translate("bot.errors.internal_error", user_id)
        )
        context.user_data.clear()
        return ConversationHandler.END
    finally:
        db.close()
