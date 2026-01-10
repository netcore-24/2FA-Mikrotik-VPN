# Telegram: сообщения и условия показа

Этот документ описывает **все сообщения**, которые отправляются пользователю через Telegram-бот, и **условия**, при которых они появляются.

## Источники сообщений

- **Пользователь → Бот**: команды и inline-кнопки (обработчики в `telegram_bot/handlers/*.py`, `telegram_bot/bot.py`)
- **Система → Пользователь**: уведомления из backend-процесса (планировщик) через `telegram_bot/services/notification_service.py`

## Меню бота (чтобы кнопки не терялись в истории)

Бот использует **постоянное меню Telegram (ReplyKeyboard)** для ключевых действий. Оно отображается **внизу чата всегда**:

- **Запросить VPN**
- **Отключить доступ к VPN**
- **Мои сессии**
- **Статус**

Для незарегистрированных пользователей показывается кнопка **“Зарегистрироваться”**.

## Блок-схема: сообщения по действиям пользователя

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
  V2 -- 2 --> V_CHOOSE["Сообщение (hardcoded):\n\"У вас привязано 2 аккаунта… выберите\"\nКнопки: action:request_vpn:<username>"]
  V2 -- 1 --> V_GO
  V_CHOOSE --> V_GO["Сообщение (hardcoded):\n\"Активирую MikroTik аккаунт: <username>…\""]
  V_GO --> V_CREATE{create_vpn_session() успешно?\n(внутри enable_user_manager_user)}
  V_CREATE -- Нет --> V_ERR["Сообщение (hardcoded):\n\"Не удалось связаться с MikroTik…\" + техническая причина"]
  V_CREATE -- Да --> V_OK["Сообщение: bot.vpn.request.success (session_id, duration)\nСообщение: bot.vpn.request.session_info"]

  %% Отключить доступ
  R0 -->|/disable_vpn или action:disable_vpn_access| D0["Отключение доступа:\n1) disconnect_vpn_session для активных сессий\n2) disable_user_manager_user для всех привязанных аккаунтов\nСообщение: сводка (hardcoded)\nЕсли MikroTik error → сообщение (hardcoded)"]

  %% Подтверждение (кнопки из уведомления 2FA)
  CF0 -->|✅ Да| CF_Y["callback: confirm_session:{session_id}:yes\nДействие: mark_session_as_confirmed\nСообщение (edit): \"✅ Подключение подтверждено…\""]
  CF0 -->|❌ Нет| CF_N["callback: confirm_session:{session_id}:no\nДействие: disconnect_vpn_session\nСообщение (edit): \"❌ Подключение отклонено…\""]

  %% Unknown command/action
  A -->|Неизвестная команда| UC["Сообщение: bot.errors.unknown_command"]
  A -->|Неизвестный callback| UA["Сообщение (edit): bot.errors.unknown_action"]
```

## Блок-схема: уведомления системы (планировщик → Telegram)

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

  %% CONNECTED timeout (нет подтверждения)
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

## Список уведомлений (шаблоны Telegram)

Шаблоны редактируются в UI: **Настройки → Telegram сообщения**.

Категория в БД: `telegram_templates`.

| Ключ настройки | Когда отправляется | Где вызывается |
|---|---|---|
| `telegram_template_confirmation_required` | Когда обнаружено подключение и нужно подтверждение (2FA) | `scheduler_service.check_vpn_connections` → `notify_session_confirmation_required` |
| `telegram_template_session_confirmed` | Когда сессия подтверждена автоматически (require_confirmation=false) | `scheduler_service.check_vpn_connections` → `notify_session_confirmed` |
| `telegram_template_session_disconnected` | Когда сессия отключена по таймауту подтверждения или когда MikroTik перестал видеть активность дольше grace | `scheduler_service.check_vpn_connections` → `notify_session_disconnected` |
| `telegram_template_session_reminder` | За 1 час до истечения `expires_at` | `scheduler_service.send_reminders` → `notify_session_reminder` |
| `telegram_template_session_expired` | Когда `expires_at < now` | `scheduler_service.check_expired_sessions` → `notify_session_expired` |

### Плейсхолдеры для шаблонов

Поддерживаются (см. `telegram_bot/services/notification_service.py`):

- `{full_name}`
- `{telegram_id}`
- `{mikrotik_username}`
- `{mikrotik_session_id}`
- `{expires_at}`
- `{hours_remaining}` (для reminder)
- `{now}`

## Важные заметки

- Уведомления об **одобрении/отклонении регистрации** сейчас **не отправляются автоматически** администратором из web UI. Статус пользователь видит через `/start` и `/status`.
- В ряде мест используются **hardcoded тексты** (например выбор из 2 аккаунтов, “активирую аккаунт…”, некоторые тексты подтверждения в callback). Их тоже стоит учитывать при кастомизации.

