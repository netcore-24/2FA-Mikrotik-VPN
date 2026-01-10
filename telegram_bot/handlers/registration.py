"""
Обработчики для регистрации пользователей.
"""
import logging
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

from backend.database import SessionLocal
from backend.services.registration_service import create_registration_request
from telegram_bot.utils.i18n import translate
from telegram_bot.middleware.auth import check_user_registered
from telegram_bot.handlers.basic import build_main_menu_keyboard

logger = logging.getLogger(__name__)

# Состояния conversation для регистрации
WAITING_FULL_NAME = "waiting_full_name"


async def register_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /register и процесса регистрации."""
    user = update.effective_user
    user_id = user.id
    message = update.message or (update.callback_query.message if update.callback_query else None)
    db = SessionLocal()
    
    try:
        # Если это callback query (кнопка), обязательно отвечаем, чтобы не висело "Loading..."
        if update.callback_query:
            await update.callback_query.answer()

        if not message:
            # На случай inline-mode callback без message
            logger.warning(f"register_handler: нет message для user_id={user_id}")
            return ConversationHandler.END

        # Проверяем, не зарегистрирован ли уже пользователь
        if check_user_registered(db, user_id):
            await message.reply_text(
                translate("bot.register.already_registered", user_id),
                reply_markup=build_main_menu_keyboard(user_id, is_registered=True),
            )
            return ConversationHandler.END
        
        awaiting_full_name = bool(context.user_data.get("awaiting_full_name"))

        if awaiting_full_name:
            # Получаем полное имя из сообщения (на этом шаге это всегда обычный текст)
            full_name = (update.message.text if update.message else "").strip()
            
            if not full_name or len(full_name) < 2:
                await message.reply_text(
                    translate("bot.register.invalid_name", user_id)
                )
                return WAITING_FULL_NAME
            
            # Создаем запрос на регистрацию
            try:
                registration_request = create_registration_request(
                    db=db,
                    telegram_id=user_id,
                    full_name=full_name,
                )
                
                # Очищаем состояние
                context.user_data.pop("awaiting_full_name", None)
                
                await message.reply_text(
                    translate("bot.register.success", user_id).format(
                        request_id=registration_request.id[:8]
                    )
                )
                await message.reply_text(
                    translate("bot.register.waiting_approval", user_id),
                    reply_markup=build_main_menu_keyboard(user_id, is_registered=False),
                )
                
                return ConversationHandler.END
                
            except Exception as e:
                logger.error(f"Ошибка при создании запроса на регистрацию: {e}", exc_info=True)
                await message.reply_text(
                    translate("bot.errors.internal_error", user_id)
                )
                return ConversationHandler.END
        
        else:
            # Начало процесса регистрации
            await message.reply_text(
                translate("bot.register.welcome", user_id)
            )
            await message.reply_text(
                translate("bot.register.ask_full_name", user_id),
                reply_markup=build_main_menu_keyboard(user_id, is_registered=False),
            )
            
            # Отмечаем, что ждём ФИО
            context.user_data["awaiting_full_name"] = True
            
            return WAITING_FULL_NAME
    
    except Exception as e:
        logger.error(f"Ошибка в register_handler: {e}", exc_info=True)
        if message:
            await message.reply_text(translate("bot.errors.internal_error", user_id))
        context.user_data.clear()
        return ConversationHandler.END
    finally:
        db.close()
