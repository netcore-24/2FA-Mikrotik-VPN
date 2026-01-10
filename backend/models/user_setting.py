"""
Модель настроек пользователя.
"""
from sqlalchemy import Column, String, ForeignKey, Integer, Text, Boolean
from sqlalchemy.orm import relationship
from .base import Base, UUIDMixin, TimestampMixin


class UserSetting(Base, UUIDMixin, TimestampMixin):
    """Настройки пользователя."""
    __tablename__ = "user_settings"
    
    user_id = Column(String(36), ForeignKey("users.id"), unique=True, nullable=False, index=True)
    firewall_rule_comment = Column(String(255), nullable=True)
    # Доп. защита: требовать подтверждение "Это вы подключились?" перед включением firewall
    require_confirmation = Column(Boolean, default=False, nullable=False)
    reminder_interval_hours = Column(Integer, default=6, nullable=False)
    # Индивидуальное время жизни VPN-сессии (в часах)
    session_duration_hours = Column(Integer, default=24, nullable=False)
    custom_notification_text = Column(Text, nullable=True)
    
    # Связи
    user = relationship("User", back_populates="user_settings")
    
    def __repr__(self):
        return f"<UserSetting(id={self.id}, user_id={self.user_id})>"
