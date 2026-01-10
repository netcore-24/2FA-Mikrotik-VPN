"""
Конфигурация приложения.
Использует pydantic-settings для управления настройками из переменных окружения.
Также может загружать настройки из базы данных для динамической конфигурации.
"""
from pydantic_settings import BaseSettings
from typing import List, Optional, Dict, Any
import os
import logging
import re

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """Настройки приложения из переменных окружения."""
    
    # Основные настройки
    APP_NAME: str = "MikroTik 2FA VPN System"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    ENVIRONMENT: str = "production"
    
    # База данных
    DATABASE_URL: str = "sqlite:///./data/mikrotik_2fa.db"
    
    # Безопасность
    SECRET_KEY: str = "change-this-secret-key-in-production"
    JWT_SECRET_KEY: Optional[str] = None  # Если не указан, используется SECRET_KEY
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 часа
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # Telegram Bot
    TELEGRAM_BOT_TOKEN: Optional[str] = None
    TELEGRAM_ADMIN_CHAT_ID: Optional[str] = None
    
    # MikroTik Router (по умолчанию, можно переопределить через БД)
    MIKROTIK_HOST: Optional[str] = None
    MIKROTIK_PORT: int = 22
    MIKROTIK_USERNAME: Optional[str] = None
    MIKROTIK_PASSWORD: Optional[str] = None
    MIKROTIK_SSH_KEY_PATH: Optional[str] = None
    MIKROTIK_USE_SSL: bool = False
    
    # Настройки сервера
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    API_PREFIX: str = "/api"
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:5173"]
    
    # Логирование
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"
    
    # Настройки системы
    TIMEZONE: str = "UTC"
    LANGUAGE: str = "ru"
    
    # Настройки резервного копирования
    BACKUP_ENABLED: bool = True
    BACKUP_INTERVAL_HOURS: int = 24
    BACKUP_RETENTION_DAYS: int = 7
    BACKUP_PATH: str = "./backups"
    
    # Шифрование для хранения чувствительных данных
    ENCRYPTION_KEY: Optional[str] = None
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        extra = "ignore"  # Игнорируем дополнительные поля из .env


# Глобальный экземпляр настроек
settings = Settings()


def load_settings_from_db() -> Dict[str, Any]:
    """
    Загрузить настройки из базы данных и обновить глобальный объект settings.
    Вызывается при старте приложения для синхронизации БД -> settings
    """
    global settings
    try:
        from backend.database import SessionLocal
        from backend.services.settings_service import get_setting_value
        
        db = SessionLocal()
        try:
            # Загружаем важные настройки из БД и обновляем глобальный settings
            db_settings = {}
            
            # Telegram Bot
            telegram_token = get_setting_value(db, "telegram_bot_token")
            if telegram_token:
                settings.TELEGRAM_BOT_TOKEN = telegram_token
                db_settings["TELEGRAM_BOT_TOKEN"] = telegram_token
                logger.info("Telegram Bot Token загружен из базы данных")
            
            # MikroTik настройки (также хранятся в БД через settings)
            mikrotik_host = get_setting_value(db, "mikrotik_host")
            if mikrotik_host:
                settings.MIKROTIK_HOST = str(mikrotik_host)
                db_settings["MIKROTIK_HOST"] = str(mikrotik_host)
            
            mikrotik_port = get_setting_value(db, "mikrotik_port")
            if mikrotik_port:
                settings.MIKROTIK_PORT = int(mikrotik_port) if str(mikrotik_port).isdigit() else 22
                db_settings["MIKROTIK_PORT"] = str(mikrotik_port)
            
            mikrotik_username = get_setting_value(db, "mikrotik_username")
            if mikrotik_username:
                settings.MIKROTIK_USERNAME = str(mikrotik_username)
                db_settings["MIKROTIK_USERNAME"] = str(mikrotik_username)
            
            mikrotik_password = get_setting_value(db, "mikrotik_password")
            if mikrotik_password:
                settings.MIKROTIK_PASSWORD = str(mikrotik_password)
                db_settings["MIKROTIK_PASSWORD"] = str(mikrotik_password)
            
            # Обновляем .env файл если настройки есть в БД
            if db_settings:
                _update_env_from_db_settings(db_settings)
            
            return db_settings
        finally:
            db.close()
    except Exception as e:
        logger.warning(f"Не удалось загрузить настройки из БД: {e}")
        return {}


def _update_env_from_db_settings(db_settings: Dict[str, Any], env_file_path: str = ".env") -> None:
    """Обновить .env файл настройками из БД."""
    try:
        env_path = os.path.join(os.getcwd(), env_file_path)
        if not os.path.exists(env_path):
            return
        
        # Читаем файл
        with open(env_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Обновляем каждую настройку
        for key, value in db_settings.items():
            # Экранируем значение
            escaped_value = str(value).replace('\\', '\\\\').replace('$', '\\$')
            
            # Ищем существующую строку или добавляем новую
            pattern = rf"^{re.escape(key)}=.*$"
            replacement = f"{key}={escaped_value}"
            
            if re.search(pattern, content, re.MULTILINE):
                content = re.sub(pattern, replacement, content, flags=re.MULTILINE)
            else:
                # Добавляем в конец файла
                if not content.endswith('\n'):
                    content += '\n'
                content += f"{replacement}\n"
        
        # Записываем обратно
        with open(env_path, 'w', encoding='utf-8') as f:
            f.write(content)
    except Exception as e:
        logger.warning(f"Не удалось обновить .env файл: {e}")
