"""
Сервис для работы с мастером настройки (Setup Wizard).
"""
from typing import Dict, Any, List, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from backend.services.auth_service import create_admin
from backend.services.settings_service import set_setting, get_setting_value
from backend.models.admin import Admin
from backend.models.mikrotik_config import MikroTikConfig
from backend.services.mikrotik_config_service import create_mikrotik_config
from backend.services.mikrotik_service import test_mikrotik_connection
from backend.models.mikrotik_config import ConnectionType
from config.settings import settings as app_settings


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
    """
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
    
    is_completed = (
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
    
    return {
        "is_completed": is_completed,
        "current_step": _get_current_step(completed_steps),
        "completed_steps": completed_steps,
        "total_steps": len(SETUP_WIZARD_STEPS),
    }


def _get_current_step(completed_steps: List[str]) -> str:
    """Определить текущий шаг мастера настройки."""
    step_order = ["basic_info", "security", "telegram_bot", "mikrotik", "notifications", "additional", "review"]
    
    for step_id in step_order:
        if step_id not in completed_steps:
            return step_id
    
    return "review"  # Если все шаги выполнены, показываем финальный шаг


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
        
        # Создаем первого администратора, если указаны данные
        if "admin_username" in data and "admin_password" in data and "admin_email" in data:
            try:
                create_admin(
                    db=db,
                    username=data["admin_username"],
                    email=data["admin_email"],
                    password=data["admin_password"],
                    full_name=data.get("admin_full_name"),
                    is_super_admin=True,
                )
            except Exception as e:
                # Администратор уже может существовать
                pass
        
        set_setting(db, "setup_wizard_security_completed", True, category="setup_wizard")
        return {"success": True, "message": "Security settings saved"}
    
    elif step_id == "telegram_bot":
        # Сохраняем настройки Telegram бота
        if "telegram_bot_token" in data:
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
            connection_type = ConnectionType(data.get("connection_type", "ssh_password"))
            
            # Проверяем, не существует ли уже активная конфигурация
            from backend.services.mikrotik_config_service import get_active_mikrotik_config
            existing_config = get_active_mikrotik_config(db)
            
            if not existing_config:
                create_mikrotik_config(
                    db=db,
                    name=data.get("mikrotik_name", "Main Router"),
                    host=data["mikrotik_host"],
                    port=data.get("mikrotik_port", 22),
                    username=data["mikrotik_username"],
                    password=data.get("mikrotik_password"),
                    ssh_key_path=data.get("mikrotik_ssh_key_path"),
                    connection_type=connection_type,
                    is_active=True,
                )
            
            # Сохраняем дополнительные настройки
            if "mikrotik_user_prefix" in data:
                set_setting(db, "mikrotik_user_prefix", data["mikrotik_user_prefix"], category="mikrotik")
            if "mikrotik_firewall_comment_template" in data:
                set_setting(db, "mikrotik_firewall_comment_template", data["mikrotik_firewall_comment_template"], category="mikrotik")
        
        set_setting(db, "setup_wizard_mikrotik_completed", True, category="setup_wizard")
        return {"success": True, "message": "MikroTik settings saved"}
    
    elif step_id == "notifications":
        # Сохраняем настройки уведомлений
        if "admin_email" in data:
            set_setting(db, "admin_email", data["admin_email"], category="notifications")
        if "telegram_admin_chat_id" in data:
            set_setting(db, "telegram_admin_chat_id", data["telegram_admin_chat_id"], category="notifications")
        if "notification_types" in data:
            set_setting(db, "notification_types", data["notification_types"], category="notifications")
        
        set_setting(db, "setup_wizard_notifications_completed", True, category="setup_wizard")
        return {"success": True, "message": "Notifications settings saved"}
    
    elif step_id == "additional":
        # Сохраняем дополнительные настройки
        if "ui_theme" in data:
            set_setting(db, "ui_theme", data["ui_theme"], category="ui")
        if "log_level" in data:
            set_setting(db, "log_level", data["log_level"], category="logging")
        if "backup_enabled" in data:
            set_setting(db, "backup_enabled", data["backup_enabled"], category="backup")
        if "backup_interval_hours" in data:
            set_setting(db, "backup_interval_hours", data["backup_interval_hours"], category="backup")
        
        set_setting(db, "setup_wizard_additional_completed", True, category="setup_wizard")
        return {"success": True, "message": "Additional settings saved"}
    
    elif step_id == "review":
        # Завершаем мастер настройки
        set_setting(db, "setup_wizard_completed", True, category="setup_wizard")
        set_setting(db, "setup_wizard_completed_at", datetime.utcnow().isoformat(), category="setup_wizard")
        return {"success": True, "message": "Setup wizard completed"}
    
    return {"success": False, "message": f"Unknown step: {step_id}"}


def restart_setup_wizard(db: Session) -> None:
    """Перезапустить мастер настройки (сбросить все шаги)."""
    steps = ["basic_info", "security", "telegram_bot", "mikrotik", "notifications", "additional"]
    for step in steps:
        set_setting(db, f"setup_wizard_{step}_completed", False, category="setup_wizard")
    set_setting(db, "setup_wizard_completed", False, category="setup_wizard")


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
