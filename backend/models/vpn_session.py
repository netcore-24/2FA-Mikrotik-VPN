"""
Модель VPN сессии.
"""
from sqlalchemy import Column, String, ForeignKey, Enum as SQLEnum, DateTime
from sqlalchemy.orm import relationship
import enum
from .base import Base, UUIDMixin, TimestampMixin


class VPNSessionStatus(str, enum.Enum):
    """Статусы VPN сессии."""
    REQUESTED = "requested"
    CONNECTED = "connected"
    CONFIRMED = "confirmed"
    ACTIVE = "active"
    REMINDER_SENT = "reminder_sent"
    EXPIRED = "expired"
    DISCONNECTED = "disconnected"


class VPNSession(Base, UUIDMixin, TimestampMixin):
    """VPN сессия пользователя."""
    __tablename__ = "vpn_sessions"
    
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    mikrotik_username = Column(String(100), nullable=False)
    # ID сессии на MikroTik (".id" из /ppp active или /user-manager session)
    mikrotik_session_id = Column(String(64), nullable=True, index=True)
    status = Column(SQLEnum(VPNSessionStatus), default=VPNSessionStatus.REQUESTED, nullable=False)
    
    connected_at = Column(DateTime, nullable=True)
    confirmed_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    reminder_sent_at = Column(DateTime, nullable=True)
    # Последний момент, когда мы видели активную сессию на MikroTik для этого username.
    # Нужен для защиты от ложных "disconnected" при кратковременных сбоях связи/учёта.
    last_seen_at = Column(DateTime, nullable=True)
    
    firewall_rule_id = Column(String(100), nullable=True)
    
    # Связи
    user = relationship("User", back_populates="vpn_sessions")
    
    def __repr__(self):
        return f"<VPNSession(id={self.id}, user_id={self.user_id}, status={self.status})>"
