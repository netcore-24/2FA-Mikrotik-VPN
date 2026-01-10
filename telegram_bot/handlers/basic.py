"""
Базовые обработчики команд (start, help, status, cancel).
"""
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ContextTypes, ConversationHandler
from sqlalchemy.orm import Session

from backend.database import SessionLocal
from telegram_bot.utils.i18n import translate
from telegram_bot.middleware.auth import check_user_registered, get_user_from_db

logger = logging.getLogger(__name__)

def build_main_menu_keyboard(user_id: int, is_registered: bool):
    """
    Постоянное меню (ReplyKeyboard) — отображается внизу Telegram и не теряется в истории сообщений.
    """
    if not is_registered:
        return ReplyKeyboardMarkup(
            [[KeyboardButton(translate("bot.buttons.register", user_id))]],
            resize_keyboard=True,
            one_time_keyboard=False,
        )

    return ReplyKeyboardMarkup(
        [
            [KeyboardButton(translate("bot.buttons.request_vpn", user_id))],
            [KeyboardButton(translate("bot.buttons.disable_vpn_access", user_id))],
            [KeyboardButton(translate("bot.buttons.my_sessions", user_id)), KeyboardButton(translate("bot.buttons.status", user_id))],
        ],
        resize_keyboard=True,
        one_time_keyboard=False,
    )


async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start."""
    user = update.effective_user
    user_id = user.id
    username = user.username or "N/A"
    logger.info(f"Получена команда /start от пользователя {user_id} (@{username})")
    
    db = SessionLocal()
    
    try:
        db_user = get_user_from_db(db, user_id)
        is_approved = check_user_registered(db, user_id)

        if is_approved:
            # Пользователь одобрен/активен
            welcome_text = translate("bot.start.welcome_registered", user_id)
            welcome_text += f"\n\n{translate('bot.start.user_info', user_id)}"
            welcome_text += f"\n{translate('bot.common.full_name', user_id)}: {db_user.full_name or 'N/A'}"
            welcome_text += f"\n{translate('bot.common.status', user_id)}: {db_user.status.value}"

            # Одно сообщение + постоянное меню (ReplyKeyboard)
            await update.message.reply_text(
                welcome_text,
                reply_markup=build_main_menu_keyboard(user_id, is_registered=True),
                parse_mode=None,
            )
            return

        # Пользователь не одобрен или вообще не создан
        welcome_text = translate("bot.start.welcome_new", user_id)
        welcome_text += f"\n\n{translate('bot.start.instructions', user_id)}"
        if db_user and db_user.status and db_user.status.value == "pending":
            welcome_text += f"\n\n{translate('bot.register.waiting_approval', user_id)}"
        elif db_user and db_user.status and db_user.status.value == "rejected":
            reason = (db_user.rejected_reason or "").strip()
            if reason:
                welcome_text += f"\n\nВаша заявка была отклонена: {reason}\nВы можете отправить новую через /register."
            else:
                welcome_text += "\n\nВаша заявка была отклонена. Вы можете отправить новую через /register."

        # Одно сообщение + меню (ReplyKeyboard)
        await update.message.reply_text(
            welcome_text,
            reply_markup=build_main_menu_keyboard(user_id, is_registered=False),
            parse_mode=None,
        )
    except Exception as e:
        logger.error(f"Ошибка в start_handler для пользователя {user_id}: {e}", exc_info=True)
        try:
            await update.message.reply_text(
                translate("bot.errors.internal_error", user_id)
            )
        except Exception as send_error:
            logger.error(f"Не удалось отправить сообщение об ошибке пользователю {user_id}: {send_error}", exc_info=True)
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

    await update.message.reply_text(
        help_text,
        parse_mode=None,
        reply_markup=build_main_menu_keyboard(user_id, is_registered=is_registered),
    )


async def status_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /status."""
    user_id = update.effective_user.id
    message = update.message or (update.callback_query.message if update.callback_query else None)
    db = SessionLocal()
    
    try:
        if update.callback_query:
            await update.callback_query.answer()

        # Проверяем регистрацию
        is_registered = check_user_registered(db, user_id)
        if not is_registered:
            await message.reply_text(
                translate("bot.errors.not_registered", user_id),
                reply_markup=build_main_menu_keyboard(user_id, is_registered=False),
            )
            return
        
        # Получаем информацию о пользователе
        db_user = get_user_from_db(db, user_id)
        if not db_user:
            await message.reply_text(
                translate("bot.errors.user_not_found", user_id),
                reply_markup=build_main_menu_keyboard(user_id, is_registered=True),
            )
            return
        
        # Формируем статус
        status_text = translate("bot.status.title", user_id)
        status_text += f"\n\n{translate('bot.common.full_name', user_id)}: {db_user.full_name}"
        status_text += f"\n{translate('bot.common.status', user_id)}: {db_user.status.value}"
        
        # username в Telegram не хранится в БД (в модели User нет поля telegram_username)
        tg_username = update.effective_user.username
        if tg_username:
            status_text += f"\n{translate('bot.common.username', user_id)}: @{tg_username}"
        
        # Получаем информацию о VPN сессиях
        from backend.services.vpn_session_service import get_user_active_sessions
        active_sessions = get_user_active_sessions(db, db_user.id)
        
        if active_sessions:
            status_text += f"\n\n{translate('bot.status.active_sessions', user_id)}: {len(active_sessions)}"
            for session in active_sessions[:3]:  # Показываем первые 3
                status_text += f"\n- {session.id[:8]}... ({session.status.value})"
        else:
            status_text += f"\n\n{translate('bot.status.no_active_sessions', user_id)}"
        
        await message.reply_text(
            status_text,
            parse_mode=None,
            reply_markup=build_main_menu_keyboard(user_id, is_registered=True),
        )
        
    except Exception as e:
        logger.error(f"Ошибка в status_handler: {e}", exc_info=True)
        if message:
            await message.reply_text(translate("bot.errors.internal_error", user_id))
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
