"""
Модель настроек пользователя.
"""
from sqlalchemy import Column, String, ForeignKey, Integer, Text
from sqlalchemy.orm import relationship
from .base import Base, UUIDMixin, TimestampMixin


class UserSetting(Base, UUIDMixin, TimestampMixin):
    """Настройки пользователя."""
    __tablename__ = "user_settings"
    
    user_id = Column(String(36), ForeignKey("users.id"), unique=True, nullable=False, index=True)
    firewall_rule_comment = Column(String(255), nullable=True)
    reminder_interval_hours = Column(Integer, default=6, nullable=False)
    custom_notification_text = Column(Text, nullable=True)
    
    # Связи
    user = relationship("User", back_populates="user_settings")
    
    def __repr__(self):
        return f"<UserSetting(id={self.id}, user_id={self.user_id})>"
