"""
Конфигурация приложения.
Использует pydantic-settings для управления настройками из переменных окружения.
"""
from pydantic_settings import BaseSettings
from typing import List, Optional
import os


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
    JWT_SECRET_KEY: str = "change-this-jwt-secret-key-in-production"
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
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


# Глобальный экземпляр настроек
settings = Settings()
