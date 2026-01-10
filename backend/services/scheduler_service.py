"""
Сервис для работы с планировщиком задач (APScheduler).
Обеспечивает фоновые операции: мониторинг VPN подключений, напоминания, проверка истекших сессий.
"""
import logging
from typing import Optional
from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.orm import Session

from backend.database import SessionLocal
from backend.services.vpn_session_service import (
    get_sessions_by_status,
    update_vpn_session_status,
    mark_session_as_expired,
    get_active_vpn_session_for_user,
)
from backend.services.mikrotik_service import get_mikrotik_users
from backend.models.vpn_session import VPNSession, VPNSessionStatus
from backend.models.user import User
from config.settings import settings

# Импортируем сервис уведомлений, если доступен
try:
    from telegram_bot.services.notification_service import (
        notify_session_confirmed,
        notify_session_disconnected,
        notify_session_expired,
        notify_session_reminder,
    )
    NOTIFICATIONS_AVAILABLE = True
except ImportError:
    NOTIFICATIONS_AVAILABLE = False
    logger.warning("Telegram notification service недоступен")

logger = logging.getLogger(__name__)


class SchedulerService:
    """Сервис для управления планировщиком задач."""
    
    def __init__(self):
        self.scheduler: Optional[AsyncIOScheduler] = None
    
    def start(self):
        """Запустить планировщик задач."""
        if self.scheduler and self.scheduler.running:
            logger.warning("Планировщик уже запущен")
            return
        
        self.scheduler = AsyncIOScheduler()
        
        # Задачи мониторинга VPN подключений (каждые 5 минут)
        self.scheduler.add_job(
            self.check_vpn_connections,
            trigger=IntervalTrigger(minutes=5),
            id="check_vpn_connections",
            replace_existing=True,
        )
        
        # Задачи проверки истекших сессий (каждые 15 минут)
        self.scheduler.add_job(
            self.check_expired_sessions,
            trigger=IntervalTrigger(minutes=15),
            id="check_expired_sessions",
            replace_existing=True,
        )
        
        # Задачи отправки напоминаний (каждый час)
        self.scheduler.add_job(
            self.send_reminders,
            trigger=IntervalTrigger(hours=1),
            id="send_reminders",
            replace_existing=True,
        )
        
        # Задачи очистки старых сессий (каждый день в 3:00)
        self.scheduler.add_job(
            self.cleanup_old_sessions,
            trigger=CronTrigger(hour=3, minute=0),
            id="cleanup_old_sessions",
            replace_existing=True,
        )
        
        self.scheduler.start()
        logger.info("Планировщик задач запущен")
    
    def stop(self):
        """Остановить планировщик задач."""
        if self.scheduler:
            self.scheduler.shutdown()
            logger.info("Планировщик задач остановлен")
    
    async def check_vpn_connections(self):
        """
        Проверить подключения к VPN через MikroTik.
        Обновляет статусы сессий на основе фактических подключений.
        """
        logger.info("Проверка VPN подключений...")
        db = SessionLocal()
        
        try:
                # Получаем все сессии со статусом CONNECTED, CONFIRMED или ACTIVE
            connected_sessions = get_sessions_by_status(
                db, [VPNSessionStatus.CONNECTED, VPNSessionStatus.CONFIRMED, VPNSessionStatus.ACTIVE]
            )
            
            if not connected_sessions:
                logger.debug("Нет активных подключенных сессий для проверки")
                return
            
            # Получаем список активных подключений из MikroTik
            try:
                mikrotik_users = get_mikrotik_users(db)
                active_usernames = {user.get("name") for user in mikrotik_users if user.get("name")}
            except Exception as e:
                logger.error(f"Ошибка при получении пользователей MikroTik: {e}")
                return
            
            # Проверяем каждую сессию
            for session in connected_sessions:
                mikrotik_username = session.mikrotik_username
                
                if mikrotik_username in active_usernames:
                    # Пользователь подключен, но статус еще не CONFIRMED
                    if session.status == VPNSessionStatus.CONNECTED:
                        # Обновляем статус на CONFIRMED и отправляем уведомление пользователю
                        update_vpn_session_status(db, session.id, VPNSessionStatus.CONFIRMED)
                        logger.info(f"Сессия {session.id} подтверждена (пользователь подключен)")
                        
                        # Отправить уведомление пользователю через Telegram бота
                        if NOTIFICATIONS_AVAILABLE:
                            try:
                                await notify_session_confirmed(session)
                            except Exception as e:
                                logger.error(f"Ошибка при отправке уведомления о подтверждении: {e}")
                else:
                    # Пользователь отключен, но статус еще показывает подключение
                    if session.status in [VPNSessionStatus.CONNECTED, VPNSessionStatus.CONFIRMED]:
                        # Обновляем статус на DISCONNECTED
                        update_vpn_session_status(db, session.id, VPNSessionStatus.DISCONNECTED)
                        logger.info(f"Сессия {session.id} отключена (пользователь не подключен)")
                        
                        # Отправить уведомление пользователю
                        if NOTIFICATIONS_AVAILABLE:
                            try:
                                await notify_session_disconnected(session)
                            except Exception as e:
                                logger.error(f"Ошибка при отправке уведомления об отключении: {e}")
        
        except Exception as e:
            logger.error(f"Ошибка при проверке VPN подключений: {e}", exc_info=True)
        finally:
            db.close()
    
    async def check_expired_sessions(self):
        """
        Проверить и отметить истекшие сессии.
        """
        logger.info("Проверка истекших сессий...")
        db = SessionLocal()
        
        try:
            # Получаем все активные сессии
            active_sessions = get_sessions_by_status(
                db,
                [
                    VPNSessionStatus.REQUESTED,
                    VPNSessionStatus.CONNECTED,
                    VPNSessionStatus.CONFIRMED,
                    VPNSessionStatus.ACTIVE,
                    VPNSessionStatus.REMINDER_SENT,
                ]
            )
            
            now = datetime.utcnow()
            expired_count = 0
            
            for session in active_sessions:
                # Проверяем, истекла ли сессия
                if session.expires_at and session.expires_at < now:
                    mark_session_as_expired(db, session.id)
                    expired_count += 1
                    logger.info(f"Сессия {session.id} отмечена как истекшая")
                    
                    # Отправить уведомление пользователю
                    if NOTIFICATIONS_AVAILABLE:
                        try:
                            await notify_session_expired(session)
                        except Exception as e:
                            logger.error(f"Ошибка при отправке уведомления об истечении: {e}")
                elif not session.expires_at:
                    # Если expires_at не установлен, устанавливаем его на основе created_at
                    # (по умолчанию 24 часа)
                    if session.created_at:
                        expires_at = session.created_at + timedelta(hours=24)
                        session.expires_at = expires_at
                        db.commit()
            
            if expired_count > 0:
                logger.info(f"Отмечено {expired_count} истекших сессий")
        
        except Exception as e:
            logger.error(f"Ошибка при проверке истекших сессий: {e}", exc_info=True)
        finally:
            db.close()
    
    async def send_reminders(self):
        """
        Отправить напоминания пользователям о продолжении работы в VPN.
        Отправляется за 1 час до истечения сессии.
        """
        logger.info("Отправка напоминаний о VPN сессиях...")
        db = SessionLocal()
        
        try:
            # Получаем активные сессии, которым скоро истекает срок
            active_sessions = get_sessions_by_status(
                db,
                [
                    VPNSessionStatus.CONFIRMED,
                    VPNSessionStatus.ACTIVE,
                ]
            )
            
            now = datetime.utcnow()
            reminder_threshold = now + timedelta(hours=1)
            reminders_sent = 0
            
            for session in active_sessions:
                # Проверяем, нужно ли отправить напоминание
                if (
                    session.expires_at
                    and session.expires_at <= reminder_threshold
                    and session.expires_at > now
                    and session.status != VPNSessionStatus.REMINDER_SENT
                ):
                    # Отправляем напоминание
                    update_vpn_session_status(db, session.id, VPNSessionStatus.REMINDER_SENT)
                    reminders_sent += 1
                    logger.info(f"Напоминание отправлено для сессии {session.id}")
                    
                    # Отправить уведомление пользователю через Telegram бота
                    if NOTIFICATIONS_AVAILABLE:
                        try:
                            # Вычисляем оставшееся время в часах
                            hours_remaining = int((session.expires_at - now).total_seconds() / 3600)
                            await notify_session_reminder(session, hours_remaining)
                        except Exception as e:
                            logger.error(f"Ошибка при отправке напоминания: {e}")
            
            if reminders_sent > 0:
                logger.info(f"Отправлено {reminders_sent} напоминаний")
        
        except Exception as e:
            logger.error(f"Ошибка при отправке напоминаний: {e}", exc_info=True)
        finally:
            db.close()
    
    async def cleanup_old_sessions(self):
        """
        Очистить старые отключенные сессии (старше 30 дней).
        """
        logger.info("Очистка старых сессий...")
        db = SessionLocal()
        
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=30)
            
            from sqlalchemy import and_
            old_sessions = db.query(VPNSession).filter(
                and_(
                    VPNSession.status == VPNSessionStatus.DISCONNECTED,
                    VPNSession.updated_at < cutoff_date,
                )
            ).all()
            
            count = len(old_sessions)
            for session in old_sessions:
                db.delete(session)
            
            db.commit()
            logger.info(f"Удалено {count} старых сессий")
        
        except Exception as e:
            logger.error(f"Ошибка при очистке старых сессий: {e}", exc_info=True)
            db.rollback()
        finally:
            db.close()
    


# Глобальный экземпляр планировщика
scheduler_service = SchedulerService()
