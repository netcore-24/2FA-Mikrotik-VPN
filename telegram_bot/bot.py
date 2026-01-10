"""
Основной файл Telegram бота.
"""
import asyncio
import logging
import sys
import os
from typing import Optional

# Добавляем корневую директорию проекта в путь
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    filters,
    ContextTypes,
)
from telegram.constants import ParseMode

from config.settings import settings
from backend.database import init_db, SessionLocal
from telegram_bot.handlers.basic import (
    start_handler,
    help_handler,
    status_handler,
    cancel_handler,
)
from telegram_bot.handlers.registration import register_handler
from telegram_bot.handlers.vpn import (
    request_vpn_handler,
    my_sessions_handler,
)
from telegram_bot.utils.i18n import get_user_language, translate
from telegram_bot.middleware.auth import check_user_registered

# Импортируем сервис уведомлений для регистрации бота
try:
    from telegram_bot.services.notification_service import set_telegram_bot
    NOTIFICATION_SERVICE_AVAILABLE = True
except ImportError:
    NOTIFICATION_SERVICE_AVAILABLE = False

# Настройка логирования
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


class TelegramBot:
    """Класс для управления Telegram ботом."""
    
    def __init__(self, token: Optional[str] = None):
        """Инициализация бота."""
        self.token = token or settings.TELEGRAM_BOT_TOKEN
        if not self.token:
            raise ValueError("TELEGRAM_BOT_TOKEN не установлен в настройках")
        
        # Создаем приложение
        self.application = Application.builder().token(self.token).build()
        
        # Регистрируем бота в сервисе уведомлений
        if NOTIFICATION_SERVICE_AVAILABLE:
            try:
                # Получаем бот из приложения для отправки уведомлений
                bot = self.application.bot
                set_telegram_bot(bot)
                logger.info("Telegram bot зарегистрирован в сервисе уведомлений")
            except Exception as e:
                logger.warning(f"Не удалось зарегистрировать бота в сервисе уведомлений: {e}")
        
        # Регистрируем обработчики
        self._register_handlers()
        
        # Инициализируем БД
        init_db()
    
    def _register_handlers(self):
        """Регистрация всех обработчиков команд и сообщений."""
        
        # Основные команды
        self.application.add_handler(CommandHandler("start", start_handler))
        self.application.add_handler(CommandHandler("help", help_handler))
        self.application.add_handler(CommandHandler("status", status_handler))
        self.application.add_handler(CommandHandler("my_sessions", my_sessions_handler))
        
        # Регистрация пользователя
        self.application.add_handler(
            ConversationHandler(
                entry_points=[CommandHandler("register", register_handler)],
                states={
                    "waiting_full_name": [
                        MessageHandler(filters.TEXT & ~filters.COMMAND, register_handler)
                    ],
                },
                fallbacks=[CommandHandler("cancel", cancel_handler)],
            )
        )
        
        # Запрос VPN подключения
        self.application.add_handler(
            ConversationHandler(
                entry_points=[CommandHandler("request_vpn", request_vpn_handler)],
                states={
                    "waiting_reason": [
                        MessageHandler(filters.TEXT & ~filters.COMMAND, request_vpn_handler)
                    ],
                },
                fallbacks=[CommandHandler("cancel", cancel_handler)],
            )
        )
        
        # Обработчик callback queries (для inline кнопок) - должен быть после других handlers
        # Добавим его позже, чтобы не конфликтовать с conversation handlers
        
        # Обработчик callback queries (для inline кнопок)
        self.application.add_handler(CallbackQueryHandler(self._handle_callback))
        
        # Обработчик неизвестных команд
        self.application.add_handler(
            MessageHandler(filters.COMMAND, self._unknown_command_handler)
        )
    
    async def _handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик callback queries от inline кнопок."""
        query = update.callback_query
        await query.answer()
        
        callback_data = query.data
        user_id = query.from_user.id
        
        # Проверяем, зарегистрирован ли пользователь
        db = SessionLocal()
        try:
            # Разбираем callback_data
            parts = callback_data.split(":")
            action = parts[0]
            
            if action == "action":
                # Действия из кнопок (register, request_vpn, etc.)
                sub_action = parts[1] if len(parts) > 1 else None
                if sub_action == "register":
                    # Инициируем регистрацию
                    from telegram_bot.handlers.registration import register_handler
                    # Создаем фиктивный Update для команды
                    await register_handler(update, context)
                elif sub_action == "request_vpn":
                    from telegram_bot.handlers.vpn import request_vpn_handler
                    await request_vpn_handler(update, context)
                elif sub_action == "my_sessions":
                    from telegram_bot.handlers.vpn import my_sessions_handler
                    await my_sessions_handler(update, context)
                elif sub_action == "status":
                    from telegram_bot.handlers.basic import status_handler
                    await status_handler(update, context)
                else:
                    await query.edit_message_text(
                        translate("bot.errors.unknown_action", user_id)
                    )
            elif action == "confirm_session":
                if not check_user_registered(db, user_id):
                    await query.edit_message_text(
                        translate("bot.errors.not_registered", user_id)
                    )
                    return
                session_id = parts[1] if len(parts) > 1 else None
                await self._handle_session_confirmation(query, session_id, db)
            elif action == "disconnect_session":
                if not check_user_registered(db, user_id):
                    await query.edit_message_text(
                        translate("bot.errors.not_registered", user_id)
                    )
                    return
                session_id = parts[1] if len(parts) > 1 else None
                await self._handle_session_disconnect(query, session_id, db)
            else:
                await query.edit_message_text(
                    translate("bot.errors.unknown_action", user_id)
                )
        except Exception as e:
            logger.error(f"Ошибка в _handle_callback: {e}", exc_info=True)
            await query.edit_message_text(
                translate("bot.errors.internal_error", user_id)
            )
        finally:
            db.close()
    
    async def _handle_session_confirmation(
        self, query, session_id: str, db
    ):
        """Обработка подтверждения VPN сессии."""
        # TODO: Реализовать подтверждение сессии
        user_id = query.from_user.id
        await query.edit_message_text(
            translate("bot.vpn.session.confirmation_pending", user_id)
        )
    
    async def _handle_session_disconnect(
        self, query, session_id: str, db
    ):
        """Обработка отключения VPN сессии."""
        user_id = query.from_user.id
        try:
            if not session_id:
                await query.edit_message_text(
                    translate("bot.errors.internal_error", user_id)
                )
                return
            
            # Получаем пользователя
            from telegram_bot.middleware.auth import get_user_from_db
            db_user = get_user_from_db(db, user_id)
            if not db_user:
                await query.edit_message_text(
                    translate("bot.errors.user_not_found", user_id)
                )
                return
            
            # Отключаем сессию
            from backend.services.vpn_session_service import disconnect_vpn_session
            session = disconnect_vpn_session(db, session_id, db_user.id)
            
            if session:
                await query.edit_message_text(
                    translate("bot.vpn.session.disconnected", user_id)
                )
            else:
                await query.edit_message_text(
                    translate("vpn.session.not_found", user_id)
                )
        except Exception as e:
            logger.error(f"Ошибка при отключении сессии: {e}", exc_info=True)
            await query.edit_message_text(
                translate("bot.errors.internal_error", user_id)
            )
    
    async def _unknown_command_handler(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Обработчик неизвестных команд."""
        user_id = update.effective_user.id
        await update.message.reply_text(
            translate("bot.errors.unknown_command", user_id)
        )
    
    async def start(self):
        """Запуск бота."""
        logger.info("Запуск Telegram бота...")
        await self.application.initialize()
        await self.application.start()
        await self.application.updater.start_polling(
            allowed_updates=Update.ALL_TYPES
        )
        logger.info("Telegram бот запущен и ожидает сообщения...")
    
    async def stop(self):
        """Остановка бота."""
        logger.info("Остановка Telegram бота...")
        await self.application.updater.stop()
        await self.application.stop()
        await self.application.shutdown()
        logger.info("Telegram бот остановлен")


async def main():
    """Главная функция для запуска бота."""
    try:
        bot = TelegramBot()
        await bot.start()
        
        # Держим бота запущенным
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        logger.info("Получен сигнал остановки...")
    except Exception as e:
        logger.error(f"Ошибка при работе бота: {e}", exc_info=True)
    finally:
        if 'bot' in locals():
            await bot.stop()


if __name__ == "__main__":
    asyncio.run(main())
