# Telegram: messages and display conditions

This document describes **all user-facing messages** sent by the Telegram bot and the **conditions** under which they appear.

## Message sources

- **User → Bot**: commands and inline buttons (handlers in `telegram_bot/handlers/*.py`, `telegram_bot/bot.py`)
- **System → User**: notifications sent from the backend process (scheduler) via `telegram_bot/services/notification_service.py`

## Bot menu (so key buttons are always visible)

The bot uses a **persistent Telegram ReplyKeyboard** for the main actions. It is always shown at the bottom of the chat:

- **Request VPN**
- **Disable VPN access**
- **My sessions**
- **Status**

For unregistered users, a **“Register”** button is shown.

## Flowchart: messages by user actions

> Note: the flowchart below uses the original key names and some original (Russian) labels, because it references translation keys and callbacks directly.

```mermaid
flowchart TD
  A[/Пользователь открывает бота или /start/] --> B{Пользователь одобрен/активен?\ncheck_user_registered()}

  B -- Нет --> U0["Сообщение: bot.start.welcome_new + bot.start.instructions\n(если pending → bot.register.waiting_approval;\nесли rejected → текст про отклонение)\nКнопка: bot.buttons.register (action:register)"]
  B -- Да --> R0["Сообщение: bot.start.welcome_registered + user_info\nКнопки ВСЕГДА:\n- bot.buttons.request_vpn (action:request_vpn)\n- bot.buttons.disable_vpn_access (action:disable_vpn_access)\n- bot.buttons.my_sessions (action:my_sessions)\n- bot.buttons.status (action:status)"]

  %% /register
  U0 -->|/register или action:register| REG0["Сообщение: bot.register.welcome\nСообщение: bot.register.ask_full_name\n(переходим в состояние WAITING_FULL_NAME)"]
  REG0 --> REG1[/Пользователь вводит ФИО/]
  REG1 --> REGV{ФИО валидно?\nlen>=2}
  REGV -- Нет --> REG_BAD["Сообщение: bot.register.invalid_name\n(остаёмся в WAITING_FULL_NAME)"]
  REGV -- Да --> REG_OK["Создаём RegistrationRequest (pending)\nСообщение: bot.register.success (request_id)\nСообщение: bot.register.waiting_approval"]

  %% /help
  A -->|/help| H0["Сообщение: bot.help.title + bot.help.commands\n+ (если зарегистрирован) bot.help.commands_registered\nиначе bot.help.commands_unregistered"]

  %% /status
  R0 -->|/status или action:status| S0["Если НЕ зарегистрирован → bot.errors.not_registered\nЕсли user не найден → bot.errors.user_not_found\nИначе: bot.status.title + данные пользователя\n+ список активных сессий (до 3) или bot.status.no_active_sessions"]

  %% /my_sessions
  R0 -->|/my_sessions или action:my_sessions| MS0["Если нет активных сессий → bot.vpn.sessions.no_active\nИначе: bot.vpn.sessions.title + bot.vpn.sessions.session_item (для каждой)\n+ для первых 5: bot.vpn.sessions.session_details + кнопка Disconnect"]
  MS0 -->|Кнопка Disconnect| MS_DISC_CB["callback: disconnect_session:{session_id}\nСообщение (edit): bot.vpn.session.disconnected\n(если не найдено: vpn.session.not_found)"]

  %% /request_vpn
  R0 -->|/request_vpn или action:request_vpn| V0["Проверки:\n- если НЕ зарегистрирован → bot.errors.not_registered\n- если user не найден → bot.errors.user_not_found\n- если статус не approved/active → bot.vpn.request.user_not_approved"]
  V0 --> V1{Есть активные сессии?}
  V1 -- Да --> V_HAS["Сообщение: bot.vpn.request.has_active_sessions (count)\nДалее до 3 раз:\n- bot.vpn.request.active_session_info + кнопка Disconnect"]
  V_HAS -->|Кнопка Disconnect| MS_DISC_CB
  V1 -- Нет --> V2{Сколько привязанных MikroTik аккаунтов?\nuser_mikrotik_accounts (is_active)}
  V2 -- 0 --> V_NOACC["Сообщение (hardcoded):\n\"Администратор должен привязать ваш MikroTik аккаунт\""]
  V2 -- 2+ --> V_CHOOSE["Сообщение (hardcoded):\n\"You have multiple accounts… choose one\"\nButtons: action:request_vpn:<username>"]
  V2 -- 1 --> V_GO
  V_CHOOSE --> V_GO["Сообщение (hardcoded):\n\"Активирую MikroTik аккаунт: <username>…\""]
  V_GO --> V_CREATE{create_vpn_session() успешно?\n(внутри enable_user_manager_user)}
  V_CREATE -- Нет --> V_ERR["Сообщение (hardcoded):\n\"Не удалось связаться с MikroTik…\" + техническая причина"]
  V_CREATE -- Да --> V_OK["Сообщение: bot.vpn.request.success (session_id, duration)\nСообщение: bot.vpn.request.session_info"]

  %% Disable access
  R0 -->|/disable_vpn или action:disable_vpn_access| D0["Отключение доступа:\n1) disconnect_vpn_session для активных сессий\n2) disable_user_manager_user для всех привязанных аккаунтов\nСообщение: сводка (hardcoded)\nЕсли MikroTik error → сообщение (hardcoded)"]

  %% Confirmation (buttons from 2FA notification)
  CF0 -->|✅ Да| CF_Y["callback: confirm_session:{session_id}:yes\nДействие: mark_session_as_confirmed\nСообщение (edit): \"✅ Подключение подтверждено…\""]
  CF0 -->|❌ Нет| CF_N["callback: confirm_session:{session_id}:no\nДействие: disconnect_vpn_session\nСообщение (edit): \"❌ Подключение отклонено…\""]

  %% Unknown command/action
  A -->|Неизвестная команда| UC["Сообщение: bot.errors.unknown_command"]
  A -->|Неизвестный callback| UA["Сообщение (edit): bot.errors.unknown_action"]
```

## Flowchart: system notifications (scheduler → Telegram)

```mermaid
flowchart TD
  T0[Scheduler: check_vpn_connections (каждые vpn_connection_check_interval_seconds)] --> T1[Получаем активные подключения с MikroTik\n(get_user_manager_sessions: UM+PPP)]
  T1 --> T2[Для каждой DB-сессии в статусах REQUESTED/CONNECTED/CONFIRMED/ACTIVE/REMINDER_SENT\nобновляем last_seen_at при наличии на MikroTik]

  %% REQUESTED -> CONNECTED
  T2 --> T3{DB-сессия REQUESTED\nи username обнаружен активным на MikroTik?}
  T3 -- Да --> T4[mark_session_as_connected\n(сохраняем mikrotik_session_id)]
  T4 --> T5{require_confirmation?\n(user_settings.require_confirmation\nили глобальный vpn_require_confirmation)}
  T5 -- Да --> CF0["notify_session_confirmation_required\nШаблон: telegram_template_confirmation_required\nКнопки: ✅ Да / ❌ Нет"]
  T5 -- Нет --> T6[mark_session_as_confirmed → ACTIVE\n(включение firewall при привязке rule)\nnotify_session_confirmed\nШаблон: telegram_template_session_confirmed]

  %% CONNECTED timeout (no confirmation)
  T2 --> T7{DB-сессия CONNECTED\nи require_confirmation=true\nи (now - connected_at) > vpn_confirmation_timeout_seconds?}
  T7 -- Да --> T8[disconnect_vpn_session\n+ notify_session_disconnected\nШаблон: telegram_template_session_disconnected]

  %% Not seen on MikroTik
  T2 --> T9{DB-сессия CONNECTED/CONFIRMED/ACTIVE/REMINDER_SENT\nи username НЕ виден на MikroTik\nдольше grace (max(30, 2*interval))?}
  T9 -- Да --> T10[disconnect_vpn_session\n+ notify_session_disconnected]

  %% Reminders
  R0[Scheduler: send_reminders (каждый час)] --> R1{expires_at <= now+1h\nи expires_at > now\nи статус != REMINDER_SENT?}
  R1 -- Да --> R2[update status → REMINDER_SENT\nnotify_session_reminder\nШаблон: telegram_template_session_reminder]

  %% Expired
  E0[Scheduler: check_expired_sessions] --> E1{expires_at < now?}
  E1 -- Да --> E2[mark_session_as_expired\nnotify_session_expired\nШаблон: telegram_template_session_expired]
```

## Notifications list (Telegram templates)

Templates can be edited in the UI: **Settings → Telegram messages**.

Database category: `telegram_templates`.

| Setting key | When it is sent | Where it is triggered |
|---|---|---|
| `telegram_template_confirmation_required` | When a connection is detected and confirmation is required (2FA) | `scheduler_service.check_vpn_connections` → `notify_session_confirmation_required` |
| `telegram_template_session_confirmed` | When a session is confirmed automatically (require_confirmation=false) | `scheduler_service.check_vpn_connections` → `notify_session_confirmed` |
| `telegram_template_session_disconnected` | When a session is disconnected due to confirmation timeout or MikroTik inactivity beyond grace | `scheduler_service.check_vpn_connections` → `notify_session_disconnected` |
| `telegram_template_session_reminder` | 1 hour before `expires_at` | `scheduler_service.send_reminders` → `notify_session_reminder` |
| `telegram_template_session_expired` | When `expires_at < now` | `scheduler_service.check_expired_sessions` → `notify_session_expired` |

### Template placeholders

Supported placeholders (see `telegram_bot/services/notification_service.py`):

- `{full_name}`
- `{telegram_id}`
- `{mikrotik_username}`
- `{mikrotik_session_id}`
- `{expires_at}`
- `{hours_remaining}` (reminder)
- `{now}`

## Notes

- Notifications about **registration approval/rejection** are currently **not sent automatically** by admins from the web UI. Users can see their status via `/start` and `/status`.
- Some places still use **hardcoded texts** (e.g. selecting 1 of 2 MikroTik accounts, “activating account…”, some callback confirmation messages). Keep this in mind when customizing messages.

