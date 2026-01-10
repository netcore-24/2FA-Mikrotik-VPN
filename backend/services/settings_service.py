"""
Сервис для работы с системными настройками.
"""
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from backend.models.setting import Setting
from cryptography.fernet import Fernet
from config.settings import settings as app_settings
import base64
import json
import os
import re
import logging

logger = logging.getLogger(__name__)
import os
import re


def _get_encryption_key() -> bytes:
    """Получить ключ шифрования из настроек."""
    secret_key = app_settings.SECRET_KEY
    # Генерируем ключ на основе SECRET_KEY
    key = base64.urlsafe_b64encode(secret_key.encode()[:32].ljust(32, b'0'))
    return key


def encrypt_value(value: str) -> str:
    """Зашифровать значение."""
    key = _get_encryption_key()
    f = Fernet(key)
    encrypted = f.encrypt(value.encode())
    return encrypted.decode()


def decrypt_value(encrypted_value: str) -> str:
    """Расшифровать значение."""
    try:
        key = _get_encryption_key()
        f = Fernet(key)
        decrypted = f.decrypt(encrypted_value.encode())
        return decrypted.decode()
    except Exception:
        return encrypted_value  # Если не удалось расшифровать, возвращаем как есть


# Алиасы для обратной совместимости
_encrypt_value = encrypt_value
_decrypt_value = decrypt_value


def get_setting_by_key(db: Session, key: str) -> Optional[Setting]:
    """Получить настройку по ключу."""
    return db.query(Setting).filter(Setting.key == key).first()


def get_settings_by_category(db: Session, category: str) -> List[Setting]:
    """Получить все настройки категории."""
    return db.query(Setting).filter(Setting.category == category).all()


def get_all_settings(db: Session) -> List[Setting]:
    """Получить все настройки."""
    return db.query(Setting).order_by(Setting.category, Setting.key).all()


def get_setting_value(db: Session, key: str, default: Optional[Any] = None) -> Optional[Any]:
    """Получить значение настройки (с расшифровкой, если необходимо)."""
    setting = get_setting_by_key(db, key)
    if not setting:
        return default
    
    value = setting.value
    if setting.is_encrypted and value:
        value = decrypt_value(value)
    
    # Попытка преобразовать в JSON, если возможно
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return value


def set_setting(
    db: Session,
    key: str,
    value: Any,
    category: str = "general",
    description: Optional[str] = None,
    is_encrypted: bool = False,
) -> Setting:
    """Установить или обновить настройку."""
    setting = get_setting_by_key(db, key)
    
    # Преобразуем значение в строку
    if isinstance(value, (dict, list)):
        value_str = json.dumps(value)
    else:
        value_str = str(value)
    
    # Шифруем, если необходимо
    if is_encrypted:
        value_str = encrypt_value(value_str)
    
    if setting:
        # Обновляем существующую настройку
        setting.value = value_str
        if category:
            setting.category = category
        if description is not None:
            setting.description = description
        setting.is_encrypted = is_encrypted
    else:
        # Создаем новую настройку
        setting = Setting(
            key=key,
            value=value_str,
            category=category,
            description=description or f"Setting: {key}",
            is_encrypted=is_encrypted,
        )
        db.add(setting)
    
    db.commit()
    db.refresh(setting)
    
    # Автоматически обновляем .env файл для важных настроек
    # Это обеспечивает синхронизацию БД <-> .env файл
    # Для зашифрованных значений используем расшифрованное значение
    value_for_env = value_str
    if is_encrypted:
        # Для зашифрованных значений (токены, пароли) расшифровываем перед записью в .env
        try:
            value_for_env = decrypt_value(value_str)
        except:
            value_for_env = None  # Если не удалось расшифровать, пропускаем
    
    if value_for_env:
        _sync_setting_to_env_file(key, value_for_env)
    
    return setting


def _sync_setting_to_env_file(key: str, value: str) -> None:
    """
    Синхронизировать настройку с .env файлом.
    Обновляет .env файл при изменении настроек через мастер настройки.
    """
    try:
        # Маппинг ключей БД на ключи .env файла
        env_key_mapping = {
            "telegram_bot_token": "TELEGRAM_BOT_TOKEN",
            "telegram_admin_chat_id": "TELEGRAM_ADMIN_CHAT_ID",
            "mikrotik_host": "MIKROTIK_HOST",
            "mikrotik_port": "MIKROTIK_PORT",
            "mikrotik_username": "MIKROTIK_USERNAME",
            "mikrotik_password": "MIKROTIK_PASSWORD",
            "secret_key": "SECRET_KEY",
            "jwt_secret_key": "JWT_SECRET_KEY",
            "encryption_key": "ENCRYPTION_KEY",
            "language": "LANGUAGE",
            "app_name": "APP_NAME",
        }
        
        env_key = env_key_mapping.get(key.lower())
        if not env_key:
            return  # Эта настройка не нужна в .env файле
        
        # Определяем путь к .env файлу (от корня проекта)
        current_file = os.path.abspath(__file__)
        # backend/services/settings_service.py -> project_root
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_file)))
        env_file_path = os.path.join(project_root, ".env")
        
        if not os.path.exists(env_file_path):
            logger.debug(f".env файл не найден: {env_file_path}, пропускаем синхронизацию")
            return
        
        # Читаем файл
        with open(env_file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        # Ищем существующую строку или добавляем новую
        updated = False
        for i, line in enumerate(lines):
            # Игнорируем комментарии и пустые строки
            stripped = line.strip()
            if not stripped or stripped.startswith('#'):
                continue
            # Ищем строку с нужным ключом (может быть с пробелами вокруг =)
            if re.match(rf'^{re.escape(env_key)}\s*=', stripped):
                # Обновляем существующую строку
                # Экранируем специальные символы
                escaped_value = str(value).replace('\\', '\\\\').replace('$', '\\$')
                lines[i] = f"{env_key}={escaped_value}\n"
                updated = True
                break
        
        if not updated:
            # Добавляем новую строку в конец файла
            escaped_value = str(value).replace('\\', '\\\\').replace('$', '\\$')
            
            # Убеждаемся что последняя строка заканчивается переводом строки
            if lines and not lines[-1].endswith('\n'):
                lines[-1] += '\n'
            
            lines.append(f"{env_key}={escaped_value}\n")
            updated = True
        
        if updated:
            # Записываем обратно
            with open(env_file_path, 'w', encoding='utf-8') as f:
                f.writelines(lines)
            logger.debug(f"Обновлен .env файл: {env_key}")
    except Exception as e:
        # Игнорируем ошибки обновления .env файла (не критично)
        logger.debug(f"Не удалось обновить .env файл для {key}: {e}")
        pass


def delete_setting(db: Session, key: str) -> bool:
    """Удалить настройку."""
    setting = get_setting_by_key(db, key)
    if not setting:
        return False
    
    db.delete(setting)
    db.commit()
    return True


def get_settings_dict(db: Session, category: Optional[str] = None) -> Dict[str, Any]:
    """
    Получить все настройки в виде словаря.
    Если указана категория - только настройки этой категории.
    """
    if category:
        settings_list = get_settings_by_category(db, category)
    else:
        settings_list = get_all_settings(db)
    
    result = {}
    for setting in settings_list:
        value = setting.value
        if setting.is_encrypted and value:
            value = decrypt_value(value)
        
        # Попытка преобразовать в JSON
        try:
            value = json.loads(value)
        except (json.JSONDecodeError, TypeError):
            pass
        
        result[setting.key] = value
    
    return result


def get_categories(db: Session) -> List[str]:
    """Получить список всех категорий настроек."""
    categories = db.query(Setting.category).distinct().all()
    return [cat[0] for cat in categories]
