"""
API endpoints для получения статистики системы.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request, Query
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime, timedelta
from backend.database import get_db
from backend.api.dependencies import get_current_admin
from backend.api.i18n_dependencies import get_translate
from backend.api.schemas import (
    StatsOverviewResponse,
    StatsUsersResponse,
    StatsSessionsResponse,
)
from backend.services.stats_service import (
    get_overview_stats,
    get_users_stats,
    get_sessions_stats,
    get_registration_requests_stats,
    get_sessions_by_period,
    get_users_by_period,
)
from backend.models.admin import Admin

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("/overview", response_model=StatsOverviewResponse)
async def get_overview_stats_endpoint(
    request: Request,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
    t=Depends(get_translate),
):
    """
    Получить общую статистику системы.
    """
    stats = get_overview_stats(db)
    
    return StatsOverviewResponse(
        total_users=stats["total_users"],
        active_users=stats["active_users"],
        pending_users=stats["pending_users"],
        total_sessions=stats["total_sessions"],
        active_sessions=stats["active_sessions"],
        total_registration_requests=stats["total_registration_requests"],
        pending_registration_requests=stats["pending_registration_requests"],
        mikrotik_active_sessions=stats.get("mikrotik_active_sessions"),
    )


@router.get("/users", response_model=StatsUsersResponse)
async def get_users_stats_endpoint(
    request: Request,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
    t=Depends(get_translate),
):
    """
    Получить статистику по пользователям.
    """
    stats = get_users_stats(db)
    
    return StatsUsersResponse(
        total=stats["total"],
        by_status=stats["by_status"],
        approved=stats["approved"],
        rejected=stats["rejected"],
        pending=stats["pending"],
        active=stats["active"],
        inactive=stats["inactive"],
    )


@router.get("/sessions", response_model=StatsSessionsResponse)
async def get_sessions_stats_endpoint(
    request: Request,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
    t=Depends(get_translate),
):
    """
    Получить статистику по VPN сессиям.
    """
    stats = get_sessions_stats(db)
    
    return StatsSessionsResponse(
        total=stats["total"],
        by_status=stats["by_status"],
        active=stats["active"],
        connected=stats["connected"],
        confirmed=stats["confirmed"],
        disconnected=stats["disconnected"],
        expired=stats["expired"],
    )


@router.get("/registration-requests")
async def get_registration_requests_stats_endpoint(
    request: Request,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
    t=Depends(get_translate),
):
    """
    Получить статистику по запросам на регистрацию.
    """
    stats = get_registration_requests_stats(db)
    return stats


@router.get("/sessions/by-period")
async def get_sessions_by_period_endpoint(
    request: Request,
    days: int = Query(7, ge=1, le=365, description="Количество дней для статистики"),
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
    t=Depends(get_translate),
):
    """
    Получить статистику сессий за период (по дням).
    """
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)
    
    stats = get_sessions_by_period(db, start_date, end_date)
    return {
        "period_days": days,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "data": stats,
    }


@router.get("/users/by-period")
async def get_users_by_period_endpoint(
    request: Request,
    days: int = Query(30, ge=1, le=365, description="Количество дней для статистики"),
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
    t=Depends(get_translate),
):
    """
    Получить статистику пользователей за период (по дням).
    """
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)
    
    stats = get_users_by_period(db, start_date, end_date)
    return {
        "period_days": days,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "data": stats,
    }
