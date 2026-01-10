"""
Модель для сопоставления пользователей Telegram и MikroTik.
"""
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from backend.models.base import Base
import uuid


class UserMapping(Base):
    """Сопоставление пользователя Telegram и MikroTik User Manager."""
    
    __tablename__ = "user_mappings"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    telegram_user_id = Column(String, ForeignKey("users.id"), nullable=False, unique=True)
    mikrotik_username = Column(String, nullable=False, unique=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationship
    user = relationship("User", back_populates="mikrotik_mapping")
    
    def __repr__(self):
        return f"<UserMapping {self.telegram_user_id} -> {self.mikrotik_username}>"
