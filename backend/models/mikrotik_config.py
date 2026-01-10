"""
Модель конфигурации MikroTik роутера.
"""
from sqlalchemy import Column, String, Integer, Boolean, Enum as SQLEnum, DateTime
from sqlalchemy.orm import relationship
import enum
from .base import Base, UUIDMixin, TimestampMixin


class ConnectionType(str, enum.Enum):
    """Типы подключения к MikroTik."""
    SSH_PASSWORD = "ssh_password"
    SSH_KEY = "ssh_key"
    REST_API = "rest_api"


class MikroTikConfig(Base, UUIDMixin, TimestampMixin):
    """Конфигурация подключения к MikroTik роутеру."""
    __tablename__ = "mikrotik_configs"
    
    name = Column(String(100), nullable=False)
    host = Column(String(255), nullable=False)
    port = Column(Integer, default=22, nullable=False)
    username = Column(String(100), nullable=False)
    password = Column(String(255), nullable=True)  # Зашифрован
    ssh_key_path = Column(String(500), nullable=True)
    connection_type = Column(SQLEnum(ConnectionType), default=ConnectionType.SSH_PASSWORD, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    
    last_connection_test = Column(DateTime, nullable=True)
    
    def __repr__(self):
        return f"<MikroTikConfig(id={self.id}, name={self.name}, host={self.host}, is_active={self.is_active})>"
