"""
Сервис для получения статистики системы.
"""
from typing import Dict, Any, List
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func
from backend.models.user import User, UserStatus
from backend.models.vpn_session import VPNSession, VPNSessionStatus
from backend.models.registration_request import RegistrationRequest, RegistrationRequestStatus
from backend.services.user_service import count_users
from backend.services.vpn_session_service import count_vpn_sessions
from backend.services.registration_service import count_registration_requests
from backend.services.mikrotik_service import MikroTikConnectionError, get_user_manager_sessions


def get_overview_stats(db: Session) -> Dict[str, Any]:
    """Получить общую статистику системы."""
    total_users = count_users(db)
    active_users = count_users(db, status=UserStatus.ACTIVE)
    pending_users = count_users(db, status=UserStatus.PENDING)
    
    total_sessions = count_vpn_sessions(db)
    active_sessions = count_vpn_sessions(db, status=VPNSessionStatus.ACTIVE)
    
    total_registration_requests = count_registration_requests(db)
    pending_registration_requests = count_registration_requests(db, status=RegistrationRequestStatus.PENDING)

    # Активные сессии на MikroTik (UM + PPP active). Это "факт подключения" на роутере.
    # Важно: MikroTik может быть не настроен/недоступен — тогда не валим общий overview.
    mikrotik_active_sessions = None
    try:
        sessions = get_user_manager_sessions(db) or []
        active = [s for s in sessions if s.get("active") is True]
        # Считаем по session_id, если есть (надежнее), иначе по (source,user)
        ids = set()
        for s in active:
            sid = s.get("mikrotik_session_id") or s.get("session-id") or s.get("session_id")
            if sid:
                ids.add(("id", str(sid)))
                continue
            ids.add(("user", str(s.get("source") or ""), str(s.get("user") or "")))
        mikrotik_active_sessions = len(ids)
    except MikroTikConnectionError:
        mikrotik_active_sessions = None
    except Exception:
        mikrotik_active_sessions = None
    
    return {
        "total_users": total_users,
        "active_users": active_users,
        "pending_users": pending_users,
        "total_sessions": total_sessions,
        "active_sessions": active_sessions,
        "total_registration_requests": total_registration_requests,
        "pending_registration_requests": pending_registration_requests,
        "mikrotik_active_sessions": mikrotik_active_sessions,
    }


def get_users_stats(db: Session) -> Dict[str, Any]:
    """Получить статистику по пользователям."""
    total = count_users(db)
    
    by_status = {}
    for status_enum in UserStatus:
        count = count_users(db, status=status_enum)
        by_status[status_enum.value] = count
    
    return {
        "total": total,
        "by_status": by_status,
        "approved": count_users(db, status=UserStatus.APPROVED),
        "rejected": count_users(db, status=UserStatus.REJECTED),
        "pending": count_users(db, status=UserStatus.PENDING),
        "active": count_users(db, status=UserStatus.ACTIVE),
        "inactive": count_users(db, status=UserStatus.INACTIVE),
    }


def get_sessions_stats(db: Session) -> Dict[str, Any]:
    """Получить статистику по VPN сессиям."""
    total = count_vpn_sessions(db)
    
    by_status = {}
    for status_enum in VPNSessionStatus:
        count = count_vpn_sessions(db, status=status_enum)
        by_status[status_enum.value] = count
    
    return {
        "total": total,
        "by_status": by_status,
        "active": count_vpn_sessions(db, status=VPNSessionStatus.ACTIVE),
        "connected": count_vpn_sessions(db, status=VPNSessionStatus.CONNECTED),
        "confirmed": count_vpn_sessions(db, status=VPNSessionStatus.CONFIRMED),
        "disconnected": count_vpn_sessions(db, status=VPNSessionStatus.DISCONNECTED),
        "expired": count_vpn_sessions(db, status=VPNSessionStatus.EXPIRED),
    }


def get_registration_requests_stats(db: Session) -> Dict[str, Any]:
    """Получить статистику по запросам на регистрацию."""
    total = count_registration_requests(db)
    pending = count_registration_requests(db, status=RegistrationRequestStatus.PENDING)
    approved = count_registration_requests(db, status=RegistrationRequestStatus.APPROVED)
    rejected = count_registration_requests(db, status=RegistrationRequestStatus.REJECTED)
    
    return {
        "total": total,
        "pending": pending,
        "approved": approved,
        "rejected": rejected,
    }


def get_sessions_by_period(
    db: Session,
    start_date: datetime,
    end_date: datetime,
) -> List[Dict[str, Any]]:
    """Получить статистику сессий за период (список по дням)."""
    query = db.query(
        func.date(VPNSession.created_at).label("date"),
        func.count(VPNSession.id).label("count")
    ).filter(
        VPNSession.created_at >= start_date,
        VPNSession.created_at <= end_date,
    ).group_by(func.date(VPNSession.created_at))
    
    result = query.order_by(func.date(VPNSession.created_at)).all()
    return [{"date": str(row.date), "count": int(row.count)} for row in result]


def get_users_by_period(
    db: Session,
    start_date: datetime,
    end_date: datetime,
) -> List[Dict[str, Any]]:
    """
    Получить статистику пользователей за период (по дням).

    Возвращает массив объектов, чтобы фронтенду было удобно строить графики:
      - created_count: сколько пользователей создано в этот день
      - approved_count: сколько пользователей одобрено в этот день (по approved_at)
    """
    created_rows = (
        db.query(
            func.date(User.created_at).label("date"),
            func.count(User.id).label("count"),
        )
        .filter(User.created_at >= start_date, User.created_at <= end_date)
        .group_by(func.date(User.created_at))
        .order_by(func.date(User.created_at))
        .all()
    )
    approved_rows = (
        db.query(
            func.date(User.approved_at).label("date"),
            func.count(User.id).label("count"),
        )
        .filter(
            User.approved_at.isnot(None),
            User.approved_at >= start_date,
            User.approved_at <= end_date,
        )
        .group_by(func.date(User.approved_at))
        .order_by(func.date(User.approved_at))
        .all()
    )

    by_date: Dict[str, Dict[str, Any]] = {}
    for row in created_rows:
        d = str(row.date)
        by_date.setdefault(d, {"date": d, "created_count": 0, "approved_count": 0})
        by_date[d]["created_count"] = int(row.count)
    for row in approved_rows:
        d = str(row.date)
        by_date.setdefault(d, {"date": d, "created_count": 0, "approved_count": 0})
        by_date[d]["approved_count"] = int(row.count)

    # Стабильный порядок (по дате)
    return [by_date[k] for k in sorted(by_date.keys())]
