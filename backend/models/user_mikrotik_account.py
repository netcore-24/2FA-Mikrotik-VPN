"""
Модель привязки пользователя системы к учетным записям MikroTik (User Manager).

Ограничение: один пользователь Telegram (users.id) может иметь максимум 2 привязки.
Это ограничение реализовано на уровне сервиса/валидации, а не на уровне БД.
"""

from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from backend.models.base import Base
import uuid


class UserMikrotikAccount(Base):
    """Привязка пользователя системы к MikroTik username."""

    __tablename__ = "user_mikrotik_accounts"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    mikrotik_username = Column(String, nullable=False, unique=True, index=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="mikrotik_accounts")

    def __repr__(self):
        return f"<UserMikrotikAccount user_id={self.user_id} mikrotik_username={self.mikrotik_username}>"

