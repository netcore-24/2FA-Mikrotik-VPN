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
from telegram.error import TimedOut
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    filters,
    ContextTypes,
)
from telegram.request import HTTPXRequest

from config.settings import settings
from backend.database import init_db, SessionLocal
from telegram_bot.handlers.basic import (
    start_handler,
    help_handler,
    status_handler,
    cancel_handler,
    build_main_menu_keyboard,
)
from telegram_bot.handlers.registration import register_handler
from telegram_bot.handlers.vpn import (
    request_vpn_handler,
    my_sessions_handler,
    disable_vpn_access_handler,
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
import os
log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, "telegram_bot.log")

# Настраиваем логирование в файл и консоль
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
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
        # Увеличиваем таймауты Telegram API, чтобы не падать на TimedOut при плохой сети
        request = HTTPXRequest(
            connect_timeout=15,
            read_timeout=45,
            write_timeout=45,
            pool_timeout=15,
        )
        self.application = Application.builder().token(self.token).request(request).build()
        
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
        # Регистрируем обработчик ошибок (иначе PTB пишет "No error handlers...")
        self.application.add_error_handler(self._error_handler)
        
        # Инициализируем БД
        init_db()
    
    def _register_handlers(self):
        """Регистрация всех обработчиков команд и сообщений."""
        logger.info("Регистрация обработчиков команд...")
        
        # Основные команды
        self.application.add_handler(CommandHandler("start", start_handler))
        logger.info("✓ Обработчик /start зарегистрирован")
        self.application.add_handler(CommandHandler("help", help_handler))
        logger.info("✓ Обработчик /help зарегистрирован")
        self.application.add_handler(CommandHandler("status", status_handler))
        logger.info("✓ Обработчик /status зарегистрирован")
        self.application.add_handler(CommandHandler("my_sessions", my_sessions_handler))
        logger.info("✓ Обработчик /my_sessions зарегистрирован")

        # Inline-кнопки для статуса/сессий (не conversation)
        self.application.add_handler(CallbackQueryHandler(status_handler, pattern=r"^action:status$"))
        self.application.add_handler(CallbackQueryHandler(my_sessions_handler, pattern=r"^action:my_sessions$"))
        
        # Регистрация пользователя
        self.application.add_handler(
            ConversationHandler(
                entry_points=[
                    CommandHandler("register", register_handler),
                    CallbackQueryHandler(register_handler, pattern=r"^action:register$"),
                ],
                states={
                    "waiting_full_name": [
                        MessageHandler(filters.TEXT & ~filters.COMMAND, register_handler)
                    ],
                },
                fallbacks=[CommandHandler("cancel", cancel_handler)],
            )
        )
        
        # Запрос VPN подключения
        self.application.add_handler(CommandHandler("request_vpn", request_vpn_handler))
        # выбор аккаунта: action:request_vpn:<username>
        self.application.add_handler(CallbackQueryHandler(request_vpn_handler, pattern=r"^action:request_vpn(?::.*)?$"))
        # Отключить доступ к VPN
        self.application.add_handler(CommandHandler("disable_vpn", disable_vpn_access_handler))
        self.application.add_handler(CallbackQueryHandler(disable_vpn_access_handler, pattern=r"^action:disable_vpn_access(?::.*)?$"))
        
        # Обработчик callback queries (для inline кнопок) - должен быть после других handlers
        # Добавим его позже, чтобы не конфликтовать с conversation handlers
        
        # Обработчик callback queries (для inline кнопок)
        self.application.add_handler(CallbackQueryHandler(self._handle_callback))
        logger.info("✓ Обработчик callback queries зарегистрирован")

        # Постоянное меню (ReplyKeyboard): обработка нажатий текстовых кнопок
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_menu_text))
        
        # Обработчик неизвестных команд
        self.application.add_handler(
            MessageHandler(filters.COMMAND, self._unknown_command_handler)
        )
        logger.info("✓ Обработчик неизвестных команд зарегистрирован")
        
        logger.info("Все обработчики успешно зарегистрированы")
    
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
            
            if action == "confirm_session":
                if not check_user_registered(db, user_id):
                    await query.edit_message_text(
                        translate("bot.errors.not_registered", user_id)
                    )
                    return
                session_id = parts[1] if len(parts) > 1 else None
                decision = parts[2] if len(parts) > 2 else None
                await self._handle_session_confirmation(query, session_id, decision, db)
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

    async def _handle_menu_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Обработка нажатий кнопок ReplyKeyboard.
        Кнопки должны быть всегда доступны внизу — без поиска по чату.
        """
        if not update.message:
            return
        user_id = update.effective_user.id
        text = (update.message.text or "").strip()

        # Если пользователь сейчас в процессе регистрации (Conversation) — не перехватываем ввод
        if context.user_data.get("awaiting_full_name"):
            return

        db = SessionLocal()
        try:
            is_registered = check_user_registered(db, user_id)

            # Тексты кнопок берём из переводов, чтобы работало на RU/EN (если добавят)
            btn_register = translate("bot.buttons.register", user_id)
            btn_request = translate("bot.buttons.request_vpn", user_id)
            btn_disable = translate("bot.buttons.disable_vpn_access", user_id)
            btn_sessions = translate("bot.buttons.my_sessions", user_id)
            btn_status = translate("bot.buttons.status", user_id)

            if text == btn_register:
                # ConversationHandler уже слушает action:register и /register,
                # поэтому просто подскажем команду и дадим меню.
                await update.message.reply_text(
                    "Введите /register для регистрации.",
                    reply_markup=build_main_menu_keyboard(user_id, is_registered=is_registered),
                )
                return

            if text == btn_request:
                await request_vpn_handler(update, context)
                return

            if text == btn_disable:
                await disable_vpn_access_handler(update, context)
                return

            if text == btn_sessions:
                await my_sessions_handler(update, context)
                return

            if text == btn_status:
                await status_handler(update, context)
                return

            # Если текст не совпал с кнопками — не спамим ошибками; оставляем как обычное сообщение.
            # (команды обработает filters.COMMAND handler)
            return
        finally:
            db.close()

    async def _error_handler(self, update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Глобальный обработчик ошибок PTB."""
        try:
            err = context.error
            if isinstance(err, TimedOut):
                # Мягкая обработка сетевых таймаутов Telegram
                if isinstance(update, Update):
                    msg = update.message or (update.callback_query.message if update.callback_query else None)
                    if msg:
                        await msg.reply_text("Ошибка сети: Telegram API не ответил вовремя. Повторите действие через несколько секунд.")
                logger.warning("Telegram API timeout", exc_info=True)
                return
        except Exception:
            # Не даем error handler упасть
            logger.error("Ошибка в error handler", exc_info=True)
    
    async def _handle_session_confirmation(
        self, query, session_id: str, decision: str, db
    ):
        """Обработка подтверждения VPN сессии (2FA подтверждение подключения)."""
        user_id = query.from_user.id
        if not session_id or decision not in {"yes", "no"}:
            await query.edit_message_text(translate("bot.errors.internal_error", user_id))
            return

        # Получаем пользователя системы
        from telegram_bot.middleware.auth import get_user_from_db
        db_user = get_user_from_db(db, user_id)
        if not db_user:
            await query.edit_message_text(translate("bot.errors.user_not_found", user_id))
            return

        from backend.services.vpn_session_service import get_vpn_session_by_id, mark_session_as_confirmed, disconnect_vpn_session

        session = get_vpn_session_by_id(db, session_id)
        if not session or session.user_id != db_user.id:
            await query.edit_message_text("Сессия не найдена или не принадлежит вам.")
            return

        if decision == "no":
            disconnect_vpn_session(db, session_id, user_id=db_user.id)
            await query.edit_message_text("❌ Подключение отклонено. Доступ к VPN отключен.")
            return

        # decision == yes
        mark_session_as_confirmed(db, session_id)
        await query.edit_message_text("✅ Подключение подтверждено. Доступ открыт (правило firewall включено, если привязано).")
    
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
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True  # Игнорируем старые обновления
        )
        logger.info("Telegram бот запущен и ожидает сообщения...")
        logger.info(f"Токен бота: {self.token[:20]}..." if self.token else "Токен не установлен")
        # Получаем информацию о боте для подтверждения
        try:
            bot_info = await self.application.bot.get_me()
            logger.info(f"Бот подключен: @{bot_info.username} ({bot_info.first_name})")
        except Exception as e:
            logger.error(f"Не удалось получить информацию о боте: {e}", exc_info=True)
    
    async def stop(self):
        """Остановка бота."""
        logger.info("Остановка Telegram бота...")
        await self.application.updater.stop()
        await self.application.stop()
        await self.application.shutdown()
        logger.info("Telegram бот остановлен")


async def main():
    """Главная функция для запуска бота."""
    bot = None
    try:
        # Загружаем настройки из базы данных перед запуском бота
        from config.settings import load_settings_from_db
        try:
            load_settings_from_db()
            logger.info("Настройки загружены из базы данных")
        except Exception as e:
            logger.warning(f"Не удалось загрузить настройки из БД: {e}")
        
        bot = TelegramBot()
        await bot.start()
        
        # Держим бота запущенным
        logger.info("Telegram бот успешно запущен и работает...")
        # Используем asyncio.Event для ожидания сигнала остановки
        stop_event = asyncio.Event()
        await stop_event.wait()  # Ожидаем бесконечно, пока не будет установлено событие
    except KeyboardInterrupt:
        logger.info("Получен сигнал остановки (KeyboardInterrupt)...")
    except Exception as e:
        logger.error(f"Ошибка при работе бота: {e}", exc_info=True)
        raise
    finally:
        if bot:
            try:
                await bot.stop()
            except Exception as stop_error:
                logger.error(f"Ошибка при остановке бота: {stop_error}", exc_info=True)


if __name__ == "__main__":
    asyncio.run(main())
