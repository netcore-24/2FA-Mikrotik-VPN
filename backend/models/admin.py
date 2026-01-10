"""
Модель администратора системы.
"""
from sqlalchemy import Column, String, Boolean, DateTime
from sqlalchemy.orm import relationship
from .base import Base, UUIDMixin, TimestampMixin


class Admin(Base, UUIDMixin, TimestampMixin):
    """Администратор системы."""
    __tablename__ = "admins"
    
    username = Column(String(100), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    is_super_admin = Column(Boolean, default=False, nullable=False)
    last_login = Column(DateTime, nullable=True)
    
    # Связи
    approved_users = relationship("User", foreign_keys="User.approved_by_id", back_populates="approved_by")
    registration_requests_reviewed = relationship("RegistrationRequest", foreign_keys="RegistrationRequest.reviewed_by_id", back_populates="reviewed_by")
    audit_logs = relationship("AuditLog", back_populates="admin")
    
    def __repr__(self):
        return f"<Admin(id={self.id}, username={self.username}, is_active={self.is_active})>"
