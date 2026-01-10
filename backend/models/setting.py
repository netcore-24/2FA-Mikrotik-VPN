"""
Модель системных настроек.
"""
from sqlalchemy import Column, String, Text, Boolean
from .base import Base, UUIDMixin, TimestampMixin


class Setting(Base, UUIDMixin, TimestampMixin):
    """Системная настройка."""
    __tablename__ = "settings"
    
    key = Column(String(100), unique=True, nullable=False, index=True)
    value = Column(Text, nullable=True)
    category = Column(String(50), nullable=False, index=True)
    description = Column(Text, nullable=True)
    is_encrypted = Column(Boolean, default=False, nullable=False)
    
    def __repr__(self):
        return f"<Setting(id={self.id}, key={self.key}, category={self.category})>"
