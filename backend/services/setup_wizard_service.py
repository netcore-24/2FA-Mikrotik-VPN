"""
Сервис для работы с мастером настройки (Setup Wizard).
"""
from typing import Dict, Any, List, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from backend.services.auth_service import create_admin, get_admin_by_username, get_password_hash, get_admin_by_username, get_password_hash
from backend.services.settings_service import set_setting, get_setting_value
from backend.models.admin import Admin
from backend.models.mikrotik_config import MikroTikConfig
from backend.services.mikrotik_config_service import create_mikrotik_config
from backend.services.mikrotik_service import test_mikrotik_connection
from backend.models.mikrotik_config import ConnectionType
from config.settings import settings as app_settings
from backend.services.settings_service import encrypt_value


# Шаги мастера настройки
SETUP_WIZARD_STEPS = [
    {
        "id": "welcome",
        "name": "Добро пожаловать",
        "description": "Введение в мастер настройки",
        "required": False,
    },
    {
        "id": "basic_info",
        "name": "Основная информация",
        "description": "Название системы, язык, часовой пояс",
        "required": True,
    },
    {
        "id": "security",
        "name": "Безопасность",
        "description": "Секретный ключ, JWT настройки, первый администратор",
        "required": True,
    },
    {
        "id": "telegram_bot",
        "name": "Telegram Bot",
        "description": "Настройка Telegram бота",
        "required": True,
    },
    {
        "id": "mikrotik",
        "name": "MikroTik Router",
        "description": "Настройка подключения к MikroTik роутеру",
        "required": True,
    },
    {
        "id": "notifications",
        "name": "Уведомления",
        "description": "Настройка уведомлений администратору",
        "required": False,
    },
    {
        "id": "additional",
        "name": "Дополнительные настройки",
        "description": "Веб-интерфейс, логирование, резервное копирование",
        "required": False,
    },
    {
        "id": "review",
        "name": "Проверка и завершение",
        "description": "Проверка всех настроек и завершение",
        "required": True,
    },
]


def get_setup_wizard_status(db: Session) -> Dict[str, Any]:
    """
    Получить статус мастера настройки.
    Определяет, завершена ли первоначальная настройка.
    Мастер настройки можно перезапускать в любое время.
    """
    # Проверяем явный флаг завершения мастера настройки
    wizard_completed_flag = get_setting_value(db, "setup_wizard_completed", default=False)
    
    # Проверяем основные критерии завершенности настройки:
    # 1. Создан хотя бы один администратор
    from backend.models.admin import Admin
    admin_count = db.query(Admin).count()
    
    # 2. Настроен Telegram Bot Token
    telegram_token = get_setting_value(db, "telegram_bot_token", default=None)
    
    # 3. Настроено подключение к MikroTik
    from backend.services.mikrotik_config_service import get_active_mikrotik_config
    mikrotik_config = get_active_mikrotik_config(db)
    
    # 4. Сохранены основные настройки безопасности
    secret_key = get_setting_value(db, "secret_key", default=None)
    
    # Мастер считается завершенным, если:
    # - Установлен явный флаг завершения ИЛИ
    # - Все обязательные компоненты настроены
    is_completed = wizard_completed_flag or (
        admin_count > 0 and
        telegram_token is not None and
        mikrotik_config is not None and
        secret_key is not None
    )
    
    # Получаем прогресс по шагам
    completed_steps = []
    if get_setting_value(db, "setup_wizard_basic_info_completed", default=False):
        completed_steps.append("basic_info")
    if get_setting_value(db, "setup_wizard_security_completed", default=False):
        completed_steps.append("security")
    if get_setting_value(db, "setup_wizard_telegram_bot_completed", default=False):
        completed_steps.append("telegram_bot")
    if get_setting_value(db, "setup_wizard_mikrotik_completed", default=False):
        completed_steps.append("mikrotik")
    if get_setting_value(db, "setup_wizard_notifications_completed", default=False):
        completed_steps.append("notifications")
    if get_setting_value(db, "setup_wizard_additional_completed", default=False):
        completed_steps.append("additional")
    
    # Определяем текущий шаг
    current_step = _get_current_step(completed_steps)
    
    # Если мастер был явно завершен ранее (флаг установлен), считаем его завершенным
    # Но все равно разрешаем перезапуск и повторное завершение через веб-интерфейс
    # Это позволяет обновлять настройки после первого завершения
    
    return {
        "is_completed": is_completed,
        "current_step": current_step,
        "completed_steps": completed_steps,
        "total_steps": len(SETUP_WIZARD_STEPS),
        "can_restart": True,  # Всегда разрешаем перезапуск
        "was_completed_before": wizard_completed_flag,  # Флаг о том, что мастер был завершен ранее
    }


def _get_current_step(completed_steps: List[str]) -> str:
    """Определить текущий шаг мастера настройки."""
    step_order = ["basic_info", "security", "telegram_bot", "mikrotik", "notifications", "additional", "review"]
    
    # Находим первый незавершенный обязательный шаг
    required_steps = ["basic_info", "security", "telegram_bot", "mikrotik"]
    for step_id in required_steps:
        if step_id not in completed_steps:
            return step_id
    
    # Если все обязательные шаги выполнены, проверяем опциональные
    optional_steps = ["notifications", "additional"]
    for step_id in optional_steps:
        if step_id not in completed_steps:
            return step_id
    
    return "review"  # Если все шаги выполнены, показываем финальный шаг


def get_admin_email_from_db(db: Session) -> Optional[str]:
    """Получить email администратора из БД для использования в настройках уведомлений."""
    # Пробуем получить из настроек (из шага security)
    admin_email = get_setting_value(db, "admin_email", default=None)
    if admin_email:
        return admin_email
    
    # Если нет в настройках, пробуем получить из таблицы администраторов
    try:
        from backend.models.admin import Admin
        admin = db.query(Admin).first()
        if admin and admin.email:
            return admin.email
    except:
        pass
    
    return None


def get_setup_wizard_steps() -> List[Dict[str, Any]]:
    """Получить список всех шагов мастера настройки."""
    return SETUP_WIZARD_STEPS


def get_setup_wizard_step(step_id: str) -> Optional[Dict[str, Any]]:
    """Получить информацию о конкретном шаге мастера настройки."""
    for step in SETUP_WIZARD_STEPS:
        if step["id"] == step_id:
            return step
    return None


def complete_setup_wizard_step(
    db: Session,
    step_id: str,
    data: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Завершить шаг мастера настройки и сохранить данные.
    """
    if step_id == "basic_info":
        # Сохраняем основную информацию
        if "app_name" in data:
            set_setting(db, "app_name", data["app_name"], category="general")
        if "language" in data:
            set_setting(db, "language", data["language"], category="general")
        if "timezone" in data:
            set_setting(db, "timezone", data["timezone"], category="general")
        if "admin_email" in data:
            set_setting(db, "admin_email", data["admin_email"], category="notifications")
        
        set_setting(db, "setup_wizard_basic_info_completed", True, category="setup_wizard")
        return {"success": True, "message": "Basic info saved"}
    
    elif step_id == "security":
        # Сохраняем настройки безопасности
        if "secret_key" in data:
            set_setting(db, "secret_key", data["secret_key"], category="security", is_encrypted=True)
        if "jwt_access_token_expire_minutes" in data:
            set_setting(db, "jwt_access_token_expire_minutes", data["jwt_access_token_expire_minutes"], category="security")
        if "jwt_refresh_token_expire_days" in data:
            set_setting(db, "jwt_refresh_token_expire_days", data["jwt_refresh_token_expire_days"], category="security")
        
        # Сохраняем email администратора в настройках для последующего использования
        if "admin_email" in data:
            set_setting(db, "admin_email", data["admin_email"], category="notifications")
        
        # Создаем или обновляем первого администратора, если указаны данные
        if "admin_username" in data and "admin_password" in data and "admin_email" in data:
            # Проверяем, существует ли администратор с таким username
            existing_admin = get_admin_by_username(db, data["admin_username"])
            
            if existing_admin:
                # Если администратор существует, обновляем его данные
                existing_admin.email = data["admin_email"]
                existing_admin.password_hash = get_password_hash(data["admin_password"])
                if "admin_full_name" in data:
                    existing_admin.full_name = data.get("admin_full_name")
                existing_admin.is_super_admin = True
                existing_admin.is_active = True
                db.commit()
                db.refresh(existing_admin)
            else:
                # Если администратор не существует, создаем нового
                try:
                    new_admin = create_admin(
                        db=db,
                        username=data["admin_username"],
                        email=data["admin_email"],
                        password=data["admin_password"],
                        full_name=data.get("admin_full_name"),
                        is_super_admin=True,
                    )
                except Exception as e:
                    # В случае ошибки откатываем транзакцию и пробрасываем исключение с более подробной информацией
                    db.rollback()
                    error_msg = str(e)
                    if "UNIQUE constraint failed" in error_msg and "username" in error_msg:
                        # Если администратор с таким username уже существует (возможно, был создан параллельно),
                        # пробуем обновить его
                        existing_admin = get_admin_by_username(db, data["admin_username"])
                        if existing_admin:
                            existing_admin.email = data["admin_email"]
                            existing_admin.password_hash = get_password_hash(data["admin_password"])
                            if "admin_full_name" in data:
                                existing_admin.full_name = data.get("admin_full_name")
                            existing_admin.is_super_admin = True
                            existing_admin.is_active = True
                            db.commit()
                            db.refresh(existing_admin)
                        else:
                            raise ValueError(f"Не удалось создать администратора: {error_msg}")
                    else:
                        raise ValueError(f"Не удалось создать администратора: {error_msg}")
        
        set_setting(db, "setup_wizard_security_completed", True, category="setup_wizard")
        return {"success": True, "message": "Security settings saved"}
    
    elif step_id == "telegram_bot":
        # Сохраняем настройки Telegram бота
        if "telegram_bot_token" in data and data["telegram_bot_token"]:
            # Сохраняем в БД (автоматически обновится .env файл через _sync_setting_to_env_file)
            set_setting(db, "telegram_bot_token", data["telegram_bot_token"], category="telegram", is_encrypted=True)
        
        if "telegram_bot_name" in data:
            set_setting(db, "telegram_bot_name", data["telegram_bot_name"], category="telegram")
        
        if "telegram_admin_chat_id" in data:
            set_setting(db, "telegram_admin_chat_id", data["telegram_admin_chat_id"], category="telegram")
        
        set_setting(db, "setup_wizard_telegram_bot_completed", True, category="setup_wizard")
        return {"success": True, "message": "Telegram bot settings saved"}
    
    elif step_id == "mikrotik":
        # Создаем конфигурацию MikroTik
        if "mikrotik_host" in data:
            # Нормализуем поля (безопасно для host/username; пароль не трогаем кроме \r\n)
            if isinstance(data.get("mikrotik_host"), str):
                data["mikrotik_host"] = data["mikrotik_host"].strip()
            if isinstance(data.get("mikrotik_username"), str):
                data["mikrotik_username"] = data["mikrotik_username"].strip()
            if isinstance(data.get("mikrotik_password"), str):
                data["mikrotik_password"] = data["mikrotik_password"].rstrip("\r\n")

            # Получаем тип подключения и нормализуем его
            connection_type_str = data.get("connection_type", "ssh_password")
            # Преобразуем возможные варианты в корректные значения enum
            if connection_type_str in {"api", "routeros_api"}:
                connection_type_str = "api"
            elif connection_type_str in {"api_ssl", "api-ssl", "routeros_api_ssl"}:
                connection_type_str = "api_ssl"
            elif connection_type_str == "ssh_key":
                connection_type_str = "ssh_key"
            else:
                connection_type_str = "ssh_password"
            
            connection_type = ConnectionType(connection_type_str)
            
            # Определяем порт по умолчанию в зависимости от типа подключения
            default_port = 22
            if connection_type == ConnectionType.API:
                default_port = 8728
            elif connection_type == ConnectionType.API_SSL:
                default_port = 8729
            port = data.get("mikrotik_port")
            if not port:
                port = default_port
            else:
                port = int(port)
            
            # Проверяем, не существует ли уже активная конфигурация
            from backend.services.mikrotik_config_service import get_active_mikrotik_config
            existing_config = get_active_mikrotik_config(db)
            
            if not existing_config:
                create_mikrotik_config(
                    db=db,
                    name=data.get("mikrotik_name", "Main Router"),
                    host=data["mikrotik_host"],
                    port=port,
                    username=data["mikrotik_username"],
                    password=data.get("mikrotik_password"),
                    ssh_key_path=data.get("mikrotik_ssh_key_path"),
                    connection_type=connection_type,
                    is_active=True,
                )
            else:
                # Обновляем существующую конфигурацию
                existing_config.host = data["mikrotik_host"]
                existing_config.port = port
                existing_config.username = data["mikrotik_username"]
                # Важно: НЕ затираем пароль пустой строкой (UI может отправлять "" при возврате на шаг).
                # Если пароль реально передан — шифруем перед сохранением.
                if "mikrotik_password" in data:
                    pw = data.get("mikrotik_password")
                    if isinstance(pw, str):
                        pw = pw.rstrip("\r\n")
                    if pw:
                        existing_config.password = encrypt_value(str(pw))
                existing_config.connection_type = connection_type
                if "mikrotik_ssh_key_path" in data:
                    existing_config.ssh_key_path = data.get("mikrotik_ssh_key_path")
                db.commit()
            
            # Сохраняем основные настройки MikroTik в БД (для синхронизации с .env)
            if "mikrotik_host" in data:
                set_setting(db, "mikrotik_host", data["mikrotik_host"], category="mikrotik")
            if port:
                set_setting(db, "mikrotik_port", str(port), category="mikrotik")
            if "mikrotik_username" in data:
                set_setting(db, "mikrotik_username", data["mikrotik_username"], category="mikrotik")
            # Важно: не затираем сохраненный пароль пустым значением.
            # Если пароль не ввели — оставляем старый в БД/настройках.
            if "mikrotik_password" in data:
                pw_setting = data.get("mikrotik_password")
                if isinstance(pw_setting, str):
                    pw_setting = pw_setting.rstrip("\r\n")
                if pw_setting:
                    set_setting(db, "mikrotik_password", pw_setting, category="mikrotik", is_encrypted=True)

            set_setting(db, "mikrotik_connection_type", connection_type.value, category="mikrotik")
            
            # Сохраняем дополнительные настройки
            if "mikrotik_user_prefix" in data:
                set_setting(db, "mikrotik_user_prefix", data["mikrotik_user_prefix"], category="mikrotik")
            if "mikrotik_firewall_comment_template" in data:
                set_setting(db, "mikrotik_firewall_comment_template", data["mikrotik_firewall_comment_template"], category="mikrotik")
        
        set_setting(db, "setup_wizard_mikrotik_completed", True, category="setup_wizard")
        return {"success": True, "message": "MikroTik settings saved"}
    
    elif step_id == "notifications":
        # Сохраняем настройки уведомлений
        notification_method = data.get("notification_method", "none")
        
        # Обрабатываем email уведомления
        if notification_method in ["email", "both"]:
            if "notification_email" in data and data["notification_email"]:
                set_setting(db, "notification_email", data["notification_email"], category="notifications")
            else:
                # Если email не указан, используем email администратора
                admin_email = get_setting_value(db, "admin_email", default=None)
                if admin_email:
                    set_setting(db, "notification_email", admin_email, category="notifications")
        elif notification_method == "none":
            # Отключаем email уведомления
            set_setting(db, "notification_email", "", category="notifications")
        
        # Обрабатываем Telegram уведомления
        if notification_method in ["telegram_bot", "telegram_other", "both"]:
            # Для telegram_bot используем основной токен
            if notification_method == "telegram_bot":
                telegram_token = get_setting_value(db, "telegram_bot_token", default=None)
                if telegram_token:
                    set_setting(db, "notification_telegram_token", telegram_token, category="notifications", is_encrypted=True)
                # Используем основной chat_id если есть
                telegram_chat_id = get_setting_value(db, "telegram_admin_chat_id", default=None)
                if telegram_chat_id:
                    set_setting(db, "notification_telegram_chat_id", telegram_chat_id, category="notifications")
            
            # Для telegram_other используем отдельный токен
            if notification_method == "telegram_other" and "telegram_other_token" in data:
                set_setting(db, "notification_telegram_token", data["telegram_other_token"], category="notifications", is_encrypted=True)
            
            if "telegram_other_chat_id" in data and data["telegram_other_chat_id"]:
                set_setting(db, "notification_telegram_chat_id", data["telegram_other_chat_id"], category="notifications")
        elif notification_method == "none":
            # Отключаем Telegram уведомления
            set_setting(db, "notification_telegram_token", "", category="notifications")
            set_setting(db, "notification_telegram_chat_id", "", category="notifications")
        
        set_setting(db, "notification_method", notification_method, category="notifications")
        
        set_setting(db, "setup_wizard_notifications_completed", True, category="setup_wizard")
        return {"success": True, "message": "Notifications settings saved"}
    
    elif step_id == "additional":
        # Сохраняем дополнительные настройки
        if "domain_name" in data:
            set_setting(db, "domain_name", data["domain_name"], category="general")
        
        if "log_level" in data:
            set_setting(db, "log_level", data["log_level"], category="logging")
        
        if "backup_enabled" in data:
            backup_enabled = data["backup_enabled"]
            if isinstance(backup_enabled, str):
                backup_enabled = backup_enabled.lower() == "true"
            set_setting(db, "backup_enabled", backup_enabled, category="backup")
        else:
            # По умолчанию включаем резервное копирование
            set_setting(db, "backup_enabled", True, category="backup")
        
        if "backup_interval_hours" in data:
            backup_interval = int(data.get("backup_interval_hours", 24))
            # Ограничиваем значение в разумных пределах
            backup_interval = max(1, min(168, backup_interval))
            set_setting(db, "backup_interval_hours", backup_interval, category="backup")
        else:
            set_setting(db, "backup_interval_hours", 24, category="backup")
        
        set_setting(db, "setup_wizard_additional_completed", True, category="setup_wizard")
        return {"success": True, "message": "Additional settings saved"}
    
    elif step_id == "review":
        # Проверяем, что все обязательные шаги выполнены перед завершением
        completed_steps = []
        if get_setting_value(db, "setup_wizard_basic_info_completed", default=False):
            completed_steps.append("basic_info")
        if get_setting_value(db, "setup_wizard_security_completed", default=False):
            completed_steps.append("security")
        if get_setting_value(db, "setup_wizard_telegram_bot_completed", default=False):
            completed_steps.append("telegram_bot")
        if get_setting_value(db, "setup_wizard_mikrotik_completed", default=False):
            completed_steps.append("mikrotik")
        
        # Получаем список обязательных шагов (без review и welcome)
        required_steps = [s["id"] for s in SETUP_WIZARD_STEPS if s.get("required", False) and s["id"] not in ["review", "welcome"]]
        
        # Проверяем, что все обязательные шаги выполнены
        missing_required = [step for step in required_steps if step not in completed_steps]
        
        if missing_required:
            # Формируем понятные названия шагов для сообщения об ошибке
            step_names = {
                "basic_info": "Основная информация",
                "security": "Безопасность",
                "telegram_bot": "Telegram бот",
                "mikrotik": "MikroTik роутер",
            }
            missing_names = [step_names.get(step, step) for step in missing_required]
            return {
                "success": False,
                "message": f"Не все обязательные шаги выполнены. Осталось завершить: {', '.join(missing_names)}. Пожалуйста, вернитесь к этим шагам и завершите их."
            }
        
        # Также проверяем, что все необходимые данные присутствуют
        from backend.models.admin import Admin
        admin_count = db.query(Admin).count()
        telegram_token = get_setting_value(db, "telegram_bot_token", default=None)
        from backend.services.mikrotik_config_service import get_active_mikrotik_config
        mikrotik_config = get_active_mikrotik_config(db)
        
        if admin_count == 0:
            return {
                "success": False,
                "message": "Не создан администратор. Пожалуйста, завершите шаг 'Безопасность' и создайте администратора."
            }
        
        if not telegram_token:
            return {
                "success": False,
                "message": "Не настроен Telegram бот. Пожалуйста, завершите шаг 'Telegram Bot'."
            }
        
        if not mikrotik_config:
            return {
                "success": False,
                "message": "Не настроено подключение к MikroTik. Пожалуйста, завершите шаг 'MikroTik Router'."
            }
        
        # Все проверки пройдены - завершаем мастер настройки
        # Разрешаем завершить мастер даже если он был завершен ранее (перезавершение)
        set_setting(db, "setup_wizard_completed", True, category="setup_wizard")
        set_setting(db, "setup_wizard_completed_at", datetime.utcnow().isoformat(), category="setup_wizard")
        return {"success": True, "message": "Setup wizard completed"}
    
    return {"success": False, "message": f"Unknown step: {step_id}"}


def restart_setup_wizard(db: Session) -> None:
    """Перезапустить мастер настройки (сбросить все шаги и флаг завершения)."""
    steps = ["basic_info", "security", "telegram_bot", "mikrotik", "notifications", "additional"]
    for step in steps:
        set_setting(db, f"setup_wizard_{step}_completed", False, category="setup_wizard")
    # Сбрасываем флаг завершения, чтобы можно было пройти мастер заново
    set_setting(db, "setup_wizard_completed", False, category="setup_wizard")
    set_setting(db, "setup_wizard_completed_at", "", category="setup_wizard")


def test_telegram_connection(token: str) -> tuple[bool, Optional[str]]:
    """
    Протестировать подключение к Telegram API с токеном.
    Возвращает (успех, сообщение об ошибке).
    """
    try:
        import requests
        response = requests.get(
            f"https://api.telegram.org/bot{token}/getMe",
            timeout=10,
        )
        if response.status_code == 200:
            data = response.json()
            if data.get("ok"):
                return True, None
            else:
                return False, data.get("description", "Unknown error")
        else:
            return False, f"HTTP {response.status_code}: {response.text}"
    except Exception as e:
        return False, str(e)
