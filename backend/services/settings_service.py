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
    return setting


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
