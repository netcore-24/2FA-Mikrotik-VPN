"""
Обработчики для работы с VPN сессиями.
"""
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from backend.database import SessionLocal
from backend.services.vpn_session_service import (
    create_vpn_session,
    get_user_active_sessions,
    disconnect_vpn_session,
)
from backend.services.mikrotik_service import MikroTikConnectionError
from backend.services.mikrotik_service import disable_user_manager_user
from backend.models.user_mikrotik_account import UserMikrotikAccount
from telegram_bot.utils.i18n import translate
from telegram_bot.middleware.auth import check_user_registered, get_user_from_db
from telegram_bot.handlers.basic import build_main_menu_keyboard

logger = logging.getLogger(__name__)

_ACCOUNTS_PAGE_SIZE = 8

def _build_accounts_keyboard(usernames: list[str], page: int = 0) -> InlineKeyboardMarkup:
    """Клавиатура выбора MikroTik-аккаунта (поддерживает 2+ аккаунтов, с пагинацией)."""
    total = len(usernames)
    if total <= 0:
        return InlineKeyboardMarkup([])

    page = max(0, int(page or 0))
    start = page * _ACCOUNTS_PAGE_SIZE
    end = min(total, start + _ACCOUNTS_PAGE_SIZE)

    rows = []
    # 2 колонки, чтобы список не был слишком длинным
    row = []
    for idx in range(start, end):
        row.append(
            InlineKeyboardButton(
                usernames[idx],
                # важно: callback должен матчиться pattern'ом request_vpn_handler
                callback_data=f"action:request_vpn:idx:{idx}",
            )
        )
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)

    nav = []
    if start > 0:
        nav.append(InlineKeyboardButton("⬅️ Назад", callback_data=f"action:request_vpn:page:{page-1}"))
    if end < total:
        nav.append(InlineKeyboardButton("➡️ Далее", callback_data=f"action:request_vpn:page:{page+1}"))
    if nav:
        rows.append(nav)

    return InlineKeyboardMarkup(rows)


async def request_vpn_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработчик команды /request_vpn.
    Требование: НЕ спрашивать причину. При запросе включать пользователя в MikroTik (User Manager).
    Если у пользователя 2 MikroTik-аккаунта — предложить выбрать.
    """
    user_id = update.effective_user.id
    message = update.message or (update.callback_query.message if update.callback_query else None)
    db = SessionLocal()
    
    try:
        if update.callback_query:
            await update.callback_query.answer()

        # Проверка регистрации
        if not check_user_registered(db, user_id):
            await message.reply_text(
                translate("bot.errors.not_registered", user_id),
                reply_markup=build_main_menu_keyboard(user_id, is_registered=False),
            )
            return
        
        # Получение пользователя
        db_user = get_user_from_db(db, user_id)
        if not db_user:
            await message.reply_text(
                translate("bot.errors.user_not_found", user_id),
                reply_markup=build_main_menu_keyboard(user_id, is_registered=True),
            )
            return
        
        # Проверка статуса пользователя
        if db_user.status.value not in ["approved", "active"]:
            await message.reply_text(
                translate("bot.vpn.request.user_not_approved", user_id),
                reply_markup=build_main_menu_keyboard(user_id, is_registered=True),
            )
            return
        
        # Если есть активные сессии — показать и завершить обработку
        active_sessions = get_user_active_sessions(db, db_user.id)
        if active_sessions:
            await message.reply_text(
                translate("bot.vpn.request.has_active_sessions", user_id).format(
                    count=len(active_sessions)
                ),
                reply_markup=build_main_menu_keyboard(user_id, is_registered=True),
            )
            for session in active_sessions[:3]:
                session_text = translate("bot.vpn.request.active_session_info", user_id).format(
                    session_id=session.id[:8],
                    status=session.status.value,
                    created_at=session.created_at.strftime("%Y-%m-%d %H:%M:%S")
                )
                keyboard = [[
                    InlineKeyboardButton(
                        translate("bot.buttons.disconnect", user_id),
                        callback_data=f"disconnect_session:{session.id}"
                    )
                ]]
                await message.reply_text(session_text, reply_markup=InlineKeyboardMarkup(keyboard))
            return

        # Получение привязанных MikroTik usernames
        accounts = (
            db.query(UserMikrotikAccount)
            .filter(UserMikrotikAccount.user_id == db_user.id, UserMikrotikAccount.is_active == True)  # noqa: E712
            .order_by(UserMikrotikAccount.created_at.asc())
            .all()
        )
        usernames = [a.mikrotik_username for a in accounts]

        chosen_username = None
        if update.callback_query and update.callback_query.data:
            cd = update.callback_query.data
            # Пагинация списка аккаунтов
            if cd.startswith("action:request_vpn:page:"):
                try:
                    page = int(cd.split("action:request_vpn:page:", 1)[1].strip() or "0")
                except Exception:
                    page = 0
                await message.reply_text(
                    "Выберите MikroTik аккаунт для активации:",
                    reply_markup=_build_accounts_keyboard(usernames, page=page),
                )
                return

            # Новый формат выбора (индекс) — безопаснее и поддерживает любые количества аккаунтов
            if cd.startswith("action:request_vpn:idx:"):
                try:
                    idx = int(cd.split("action:request_vpn:idx:", 1)[1].strip())
                except Exception:
                    idx = -1
                if 0 <= idx < len(usernames):
                    chosen_username = usernames[idx]

            # Backward-compat: старый формат action:request_vpn:<username>
            if chosen_username is None and cd.startswith("action:request_vpn:"):
                tail = cd.split("action:request_vpn:", 1)[1].strip()
                # избегаем перехвата "idx:" и "page:" как username
                if not (tail.startswith("idx:") or tail.startswith("page:")):
                    chosen_username = tail

        if chosen_username is None:
            if len(usernames) == 1:
                chosen_username = usernames[0]
            elif len(usernames) > 1:
                await message.reply_text(
                    "У вас привязано несколько MikroTik аккаунтов.\nВыберите, какой активировать для подключения:",
                    reply_markup=_build_accounts_keyboard(usernames, page=0),
                )
                return
            else:
                await message.reply_text(
                    "Для подключения администратор должен привязать ваш MikroTik аккаунт.",
                    reply_markup=build_main_menu_keyboard(user_id, is_registered=True),
                )
                return

        # Создание VPN-сессии без указания причины (create_vpn_session включает пользователя в MikroTik)
        try:
            vpn_session = create_vpn_session(
                db=db,
                user_id=db_user.id,
                mikrotik_username=chosen_username,
                duration_hours=24,
            )
        except MikroTikConnectionError as e:
            await message.reply_text(
                "Не удалось связаться с MikroTik или активировать ваш аккаунт.\n"
                "Сообщите администратору и попробуйте позже.\n\n"
                f"Техническая причина: {str(e)}"
            )
            return
        except Exception as e:
            logger.error(f"Ошибка при создании VPN сессии: {e}", exc_info=True)
            await message.reply_text(translate("bot.errors.internal_error", user_id))
            return
        # ОДНО сообщение вместо 2-3, чтобы не спамить чат
        await message.reply_text(
            (
                f"✅ MikroTik аккаунт активирован: `{chosen_username}`\n"
                f"ID запроса: `{vpn_session.id[:8]}`\n\n"
                "Теперь подключайтесь к VPN обычным способом.\n"
                "Система обнаружит подключение и (если включена доп. защита) запросит подтверждение."
            ),
            parse_mode="Markdown",
            reply_markup=build_main_menu_keyboard(user_id, is_registered=True),
        )
    
    except Exception as e:
        logger.error(f"Ошибка в request_vpn_handler: {e}", exc_info=True)
        if message:
            await message.reply_text(translate("bot.errors.internal_error", user_id))
    finally:
        db.close()


async def my_sessions_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /my_sessions для просмотра активных сессий пользователя."""
    user_id = update.effective_user.id
    message = update.message or (update.callback_query.message if update.callback_query else None)
    db = SessionLocal()
    
    try:
        if update.callback_query:
            await update.callback_query.answer()

        # Проверка регистрации
        if not check_user_registered(db, user_id):
            await message.reply_text(
                translate("bot.errors.not_registered", user_id),
                reply_markup=build_main_menu_keyboard(user_id, is_registered=False),
            )
            return
        
        # Получение пользователя
        db_user = get_user_from_db(db, user_id)
        if not db_user:
            await message.reply_text(
                translate("bot.errors.user_not_found", user_id),
                reply_markup=build_main_menu_keyboard(user_id, is_registered=True),
            )
            return
        
        # Получение активных сессий
        active_sessions = get_user_active_sessions(db, db_user.id)
        
        if not active_sessions:
            await message.reply_text(
                translate("bot.vpn.sessions.no_active", user_id),
                reply_markup=build_main_menu_keyboard(user_id, is_registered=True),
            )
            return
        
        # ОДНО сообщение со списком + кнопками (без пачки отдельных сообщений)
        sessions_text = translate("bot.vpn.sessions.title", user_id).format(count=len(active_sessions)) + "\n\n"
        keyboard = []
        for session in active_sessions[:5]:
            session_label = session.mikrotik_session_id or (session.id[:8] + "…")
            sessions_text += translate("bot.vpn.sessions.session_item", user_id).format(
                session_id=session_label,
                status=session.status.value,
                created_at=session.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            ) + "\n"
            keyboard.append(
                [
                    InlineKeyboardButton(
                        f"{translate('bot.buttons.disconnect', user_id)} {session_label}",
                        callback_data=f"disconnect_session:{session.id}",
                    )
                ]
            )

        await message.reply_text(
            sessions_text.strip(),
            reply_markup=InlineKeyboardMarkup(keyboard) if keyboard else None,
        )
        # меню и так постоянно отображается (ReplyKeyboard)
        
    except Exception as e:
        logger.error(f"Ошибка в my_sessions_handler: {e}", exc_info=True)
        if message:
            await message.reply_text(translate("bot.errors.internal_error", user_id))
    finally:
        db.close()


async def disable_vpn_access_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Отключить доступ к VPN для пользователя:
    Предлагает выбор:
    1) Полностью отключить: разорвать все активные сессии + отключить аккаунты
    2) Отозвать доступ: отключить аккаунты, но НЕ разрывать текущие подключения
    """
    user_id = update.effective_user.id
    message = update.message or (update.callback_query.message if update.callback_query else None)
    db = SessionLocal()

    try:
        if update.callback_query:
            await update.callback_query.answer()

        mode = None
        if update.callback_query and update.callback_query.data:
            cd = update.callback_query.data
            if cd.startswith("action:disable_vpn_access:"):
                mode = cd.split("action:disable_vpn_access:", 1)[1].strip()

        if not check_user_registered(db, user_id):
            await message.reply_text(
                translate("bot.errors.not_registered", user_id),
                reply_markup=build_main_menu_keyboard(user_id, is_registered=False),
            )
            return

        db_user = get_user_from_db(db, user_id)
        if not db_user:
            await message.reply_text(
                translate("bot.errors.user_not_found", user_id),
                reply_markup=build_main_menu_keyboard(user_id, is_registered=True),
            )
            return

        if mode not in {"disconnect_all", "revoke_only"}:
            keyboard = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "🔌 Отключить ВСЕ сессии (разорвать подключения)",
                            callback_data="action:disable_vpn_access:disconnect_all",
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            "🔒 Отозвать доступ (оставить подключения активными)",
                            callback_data="action:disable_vpn_access:revoke_only",
                        )
                    ],
                ]
            )
            await message.reply_text(
                "Выберите действие:",
                reply_markup=keyboard,
            )
            return

        # Список привязанных MikroTik usernames (может быть 2+)
        accounts = (
            db.query(UserMikrotikAccount)
            .filter(UserMikrotikAccount.user_id == db_user.id, UserMikrotikAccount.is_active == True)  # noqa: E712
            .order_by(UserMikrotikAccount.created_at.asc())
            .all()
        )
        usernames = [a.mikrotik_username for a in accounts]

        disconnected = 0
        if mode == "disconnect_all":
            # 1) Разрываем активные сессии (это также выключит доступ на MikroTik и принудительно завершит соединение)
            active_sessions = get_user_active_sessions(db, db_user.id)
            for s in active_sessions:
                try:
                    disconnect_vpn_session(db, s.id, user_id=db_user.id)
                    disconnected += 1
                except Exception:
                    pass

        # 2) Всегда выключаем аккаунты (это “отзыв доступа”; при revoke_only текущие PPP/UM подключения могут остаться активными)
        disabled_ok = []
        disabled_fail = []
        for u in usernames:
            try:
                disable_user_manager_user(db, u)
                disabled_ok.append(u)
            except Exception as e:
                disabled_fail.append((u, str(e)))

        text = "Готово.\n"
        if mode == "disconnect_all":
            text += "Режим: отключить ВСЕ сессии (разорвать подключения).\n"
        else:
            text += "Режим: отозвать доступ (подключения не разрываются).\n"
        if disconnected:
            text += f"\nАктивных сессий отключено: {disconnected}"
        if disabled_ok:
            text += "\n\nОтключены MikroTik аккаунты:\n- " + "\n- ".join(disabled_ok)
        if not disabled_ok and not disabled_fail and not disconnected:
            text += "\n\nНет активных сессий и нет привязанных MikroTik аккаунтов."
        if disabled_fail:
            text += "\n\nНе удалось отключить некоторые аккаунты:\n"
            for u, err in disabled_fail:
                text += f"- {u}: {err}\n"

        await message.reply_text(
            text,
            reply_markup=build_main_menu_keyboard(user_id, is_registered=True),
        )
    except MikroTikConnectionError as e:
        await message.reply_text(
            "Не удалось связаться с MikroTik, доступ мог остаться активным.\n"
            f"Техническая причина: {str(e)}",
            reply_markup=build_main_menu_keyboard(user_id, is_registered=True),
        )
    except Exception as e:
        logger.error(f"Ошибка в disable_vpn_access_handler: {e}", exc_info=True)
        if message:
            await message.reply_text(translate("bot.errors.internal_error", user_id))
    finally:
        db.close()
