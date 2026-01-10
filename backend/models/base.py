"""
Базовая модель для всех моделей базы данных.
"""
from sqlalchemy import Column, DateTime, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
import uuid

Base = declarative_base()


class TimestampMixin:
    """Mixin для добавления полей created_at и updated_at."""
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)


class UUIDMixin:
    """Mixin для добавления поля id типа UUID (хранится как строка для совместимости с SQLite)."""
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), nullable=False)
