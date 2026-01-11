"""
Сервис для работы с конфигурациями MikroTik в базе данных.
"""
from typing import Optional, List
from datetime import datetime
from sqlalchemy.orm import Session
from backend.models.mikrotik_config import MikroTikConfig, ConnectionType
from backend.services.settings_service import encrypt_value, decrypt_value, set_setting


def _sync_active_mikrotik_connection_type_setting(db: Session, config: MikroTikConfig) -> None:
    """
    Синхронизировать тип подключения активного MikroTik-конфига в таблицу настроек.

    Это нужно, чтобы в UI -> "Настройки" было видно, чем реально подключаемся (ssh/api).
    """
    try:
        if not config or not getattr(config, "is_active", False):
            return
        set_setting(db, "mikrotik_connection_type", config.connection_type.value, category="mikrotik")
    except Exception:
        # не блокируем создание/обновление конфига из-за настроек
        pass


def get_mikrotik_config_by_id(db: Session, config_id: str) -> Optional[MikroTikConfig]:
    """Получить конфигурацию MikroTik по ID."""
    return db.query(MikroTikConfig).filter(MikroTikConfig.id == config_id).first()


def get_active_mikrotik_config(db: Session) -> Optional[MikroTikConfig]:
    """Получить активную конфигурацию MikroTik."""
    return db.query(MikroTikConfig).filter(MikroTikConfig.is_active == True).first()


def get_all_mikrotik_configs(db: Session) -> List[MikroTikConfig]:
    """Получить все конфигурации MikroTik."""
    return db.query(MikroTikConfig).order_by(MikroTikConfig.name).all()


def create_mikrotik_config(
    db: Session,
    name: str,
    host: str,
    port: int,
    username: str,
    password: Optional[str] = None,
    ssh_key_path: Optional[str] = None,
    connection_type: ConnectionType = ConnectionType.SSH_PASSWORD,
    is_active: bool = False,
) -> MikroTikConfig:
    """Создать новую конфигурацию MikroTik."""
    # Если эта конфигурация должна быть активной, деактивируем все остальные
    if is_active:
        db.query(MikroTikConfig).update({MikroTikConfig.is_active: False})
    
    # Шифруем пароль, если указан
    encrypted_password = None
    if password:
        encrypted_password = encrypt_value(password)
    
    config = MikroTikConfig(
        name=name,
        host=host,
        port=port,
        username=username,
        password=encrypted_password,
        ssh_key_path=ssh_key_path,
        connection_type=connection_type,
        is_active=is_active,
    )
    db.add(config)
    db.commit()
    db.refresh(config)
    _sync_active_mikrotik_connection_type_setting(db, config)
    return config


def update_mikrotik_config(
    db: Session,
    config_id: str,
    name: Optional[str] = None,
    host: Optional[str] = None,
    port: Optional[int] = None,
    username: Optional[str] = None,
    password: Optional[str] = None,
    ssh_key_path: Optional[str] = None,
    connection_type: Optional[ConnectionType] = None,
    is_active: Optional[bool] = None,
) -> Optional[MikroTikConfig]:
    """Обновить конфигурацию MikroTik."""
    config = get_mikrotik_config_by_id(db, config_id)
    if not config:
        return None
    
    # Если эта конфигурация должна стать активной, деактивируем все остальные
    if is_active is True:
        db.query(MikroTikConfig).filter(MikroTikConfig.id != config_id).update({MikroTikConfig.is_active: False})
    
    if name is not None:
        config.name = name
    if host is not None:
        config.host = host
    if port is not None:
        config.port = port
    if username is not None:
        config.username = username
    if password is not None:
        # Шифруем новый пароль
        config.password = encrypt_value(password)
    if ssh_key_path is not None:
        config.ssh_key_path = ssh_key_path
    if connection_type is not None:
        config.connection_type = connection_type
    if is_active is not None:
        config.is_active = is_active
    
    db.commit()
    db.refresh(config)
    _sync_active_mikrotik_connection_type_setting(db, config)
    return config


def delete_mikrotik_config(db: Session, config_id: str) -> bool:
    """Удалить конфигурацию MikroTik."""
    config = get_mikrotik_config_by_id(db, config_id)
    if not config:
        return False
    
    db.delete(config)
    db.commit()
    return True


def test_mikrotik_config_connection(db: Session, config_id: str) -> tuple[bool, Optional[str]]:
    """Протестировать подключение к MikroTik для указанной конфигурации."""
    config = get_mikrotik_config_by_id(db, config_id)
    if not config:
        return False, "Configuration not found"
    
    # Расшифровываем пароль
    password = None
    if config.password:
        try:
            password = decrypt_value(config.password)
        except Exception:
            password = config.password  # Если не удалось расшифровать, используем как есть
    
    from backend.services.mikrotik_service import test_mikrotik_connection
    
    success, error = test_mikrotik_connection(
        host=config.host,
        port=config.port,
        username=config.username,
        password=password,
        ssh_key_path=config.ssh_key_path,
        connection_type=config.connection_type,
    )
    
    # Обновляем время последнего теста
    if success:
        config.last_connection_test = datetime.utcnow()
        db.commit()
    
    return success, error


def get_mikrotik_config_with_decrypted_password(db: Session, config_id: str) -> Optional[dict]:
    """Получить конфигурацию с расшифрованным паролем (только для использования внутри системы)."""
    config = get_mikrotik_config_by_id(db, config_id)
    if not config:
        return None
    
    password = None
    if config.password:
        try:
            password = decrypt_value(config.password)
        except Exception:
            password = config.password
    
    return {
        "id": config.id,
        "name": config.name,
        "host": config.host,
        "port": config.port,
        "username": config.username,
        "password": password,
        "ssh_key_path": config.ssh_key_path,
        "connection_type": config.connection_type.value,
        "is_active": config.is_active,
        "last_connection_test": config.last_connection_test,
    }
