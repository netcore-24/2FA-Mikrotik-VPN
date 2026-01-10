"""
Базовые импорты для базы данных.
"""
from backend.models.base import Base
from backend.models import (
    User,
    Admin,
    VPNSession,
    RegistrationRequest,
    MikroTikConfig,
    Setting,
    UserSetting,
    AuditLog,
)

__all__ = ["Base"]
