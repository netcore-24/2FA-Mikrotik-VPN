"""
Модель запроса на регистрацию.
"""
from sqlalchemy import Column, String, ForeignKey, Enum as SQLEnum, DateTime, Text
from sqlalchemy.orm import relationship
import enum
from .base import Base, UUIDMixin, TimestampMixin


class RegistrationRequestStatus(str, enum.Enum):
    """Статусы запроса на регистрацию."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class RegistrationRequest(Base, UUIDMixin, TimestampMixin):
    """Запрос на регистрацию пользователя."""
    __tablename__ = "registration_requests"
    
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    status = Column(SQLEnum(RegistrationRequestStatus), default=RegistrationRequestStatus.PENDING, nullable=False)
    
    requested_at = Column(DateTime, nullable=False)
    reviewed_by_id = Column(String(36), ForeignKey("admins.id"), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    rejection_reason = Column(Text, nullable=True)
    
    # Связи
    user = relationship("User", back_populates="registration_requests")
    reviewed_by = relationship("Admin", foreign_keys=[reviewed_by_id], back_populates="registration_requests_reviewed")
    
    def __repr__(self):
        return f"<RegistrationRequest(id={self.id}, user_id={self.user_id}, status={self.status})>"
