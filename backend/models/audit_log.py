"""
Модель журнала аудита.
"""
from sqlalchemy import Column, String, ForeignKey, Text
from sqlalchemy.orm import relationship
from .base import Base, UUIDMixin, TimestampMixin


class AuditLog(Base, UUIDMixin, TimestampMixin):
    """Запись в журнале аудита."""
    __tablename__ = "audit_logs"
    
    user_id = Column(String(36), ForeignKey("users.id"), nullable=True, index=True)
    admin_id = Column(String(36), ForeignKey("admins.id"), nullable=True, index=True)
    action = Column(String(100), nullable=False, index=True)
    entity_type = Column(String(50), nullable=True)
    entity_id = Column(String(36), nullable=True)
    details = Column(Text, nullable=True)  # JSON данные
    ip_address = Column(String(45), nullable=True)
    
    # Связи
    admin = relationship("Admin", back_populates="audit_logs")
    
    def __repr__(self):
        return f"<AuditLog(id={self.id}, action={self.action}, created_at={self.created_at})>"
