"""
Модель пользователя системы.
"""
from sqlalchemy import Column, String, BigInteger, Text, ForeignKey, Enum as SQLEnum, DateTime
from sqlalchemy.orm import relationship
import enum
from .base import Base, UUIDMixin, TimestampMixin


class UserStatus(str, enum.Enum):
    """Статусы пользователя."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    ACTIVE = "active"
    INACTIVE = "inactive"


class User(Base, UUIDMixin, TimestampMixin):
    """Пользователь системы."""
    __tablename__ = "users"
    
    telegram_id = Column(BigInteger, unique=True, nullable=False, index=True)
    full_name = Column(String(255), nullable=True)
    phone = Column(String(20), nullable=True)
    email = Column(String(255), nullable=True)
    status = Column(SQLEnum(UserStatus), default=UserStatus.PENDING, nullable=False)
    rejected_reason = Column(Text, nullable=True)
    
    # Связь с администратором, который одобрил регистрацию
    approved_by_id = Column(String(36), ForeignKey("admins.id"), nullable=True)
    approved_at = Column(DateTime, nullable=True)
    
    # Связи
    approved_by = relationship("Admin", foreign_keys=[approved_by_id], back_populates="approved_users")
    vpn_sessions = relationship("VPNSession", back_populates="user", cascade="all, delete-orphan")
    registration_requests = relationship("RegistrationRequest", back_populates="user", cascade="all, delete-orphan")
    user_settings = relationship("UserSetting", back_populates="user", uselist=False, cascade="all, delete-orphan")
    # Legacy: старое сопоставление (1:1). Оставлено для обратной совместимости.
    mikrotik_mapping = relationship("UserMapping", back_populates="user", uselist=False, cascade="all, delete-orphan")
    # Привязка нескольких MikroTik-аккаунтов на пользователя
    mikrotik_accounts = relationship("UserMikrotikAccount", back_populates="user", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<User(id={self.id}, telegram_id={self.telegram_id}, status={self.status})>"
