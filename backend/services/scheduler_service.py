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
    disconnect_vpn_session,
    mark_session_as_confirmed,
    mark_session_as_connected,
)
from backend.services.mikrotik_service import get_user_manager_sessions
from backend.models.vpn_session import VPNSession, VPNSessionStatus
from backend.models.user import User
from config.settings import settings
from backend.services.settings_service import get_setting_value

logger = logging.getLogger(__name__)
uvicorn_logger = logging.getLogger("uvicorn.error")

# Импортируем сервис уведомлений, если доступен
try:
    from telegram_bot.services.notification_service import (
        notify_session_confirmed,
        notify_session_disconnected,
        notify_session_expired,
        notify_session_reminder,
        notify_session_confirmation_required,
    )
    NOTIFICATIONS_AVAILABLE = True
except ImportError:
    NOTIFICATIONS_AVAILABLE = False
    logger.warning("Telegram notification service недоступен")


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

        # Интервал проверки подключений (секунды) — из настроек, иначе дефолт 60s
        db = SessionLocal()
        try:
            check_interval_seconds = int(get_setting_value(db, "vpn_connection_check_interval_seconds", 60) or 60)
        except Exception:
            check_interval_seconds = 60
        finally:
            db.close()

        # Логируем в оба логгера: uvicorn.error точно попадает в journal/systemd.
        msg = f"Планировщик задач: интервал проверки VPN подключений = {check_interval_seconds}s"
        logger.info(msg)
        uvicorn_logger.info(msg)
        
        # Задачи мониторинга VPN подключений (по умолчанию каждую минуту)
        self.scheduler.add_job(
            self.check_vpn_connections,
            trigger=IntervalTrigger(seconds=check_interval_seconds),
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
        # Отключено по умолчанию, чтобы не раздражать пользователей частыми сообщениями.
        # (Напоминания можно вернуть позже через отдельную настройку.)
        # self.scheduler.add_job(
        #     self.send_reminders,
        #     trigger=IntervalTrigger(hours=1),
        #     id="send_reminders",
        #     replace_existing=True,
        # )
        
        # Задачи очистки старых сессий (каждый день в 3:00)
        self.scheduler.add_job(
            self.cleanup_old_sessions,
            trigger=CronTrigger(hour=3, minute=0),
            id="cleanup_old_sessions",
            replace_existing=True,
        )
        
        self.scheduler.start()
        logger.info("Планировщик задач запущен")
        uvicorn_logger.info("Планировщик задач запущен")
    
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
            # Настройка: глобально требовать ли подтверждение от пользователя ("Это вы подключились?")
            global_require_confirmation = bool(get_setting_value(db, "vpn_require_confirmation", False))
            confirmation_timeout_seconds = int(get_setting_value(db, "vpn_confirmation_timeout_seconds", 300) or 300)

            # Берем все релевантные сессии (включая REQUESTED, чтобы отловить факт подключения)
            connected_sessions = get_sessions_by_status(
                db,
                [
                    VPNSessionStatus.REQUESTED,
                    VPNSessionStatus.CONNECTED,
                    VPNSessionStatus.CONFIRMED,
                    VPNSessionStatus.ACTIVE,
                    VPNSessionStatus.REMINDER_SENT,
                ],
            )
            
            if not connected_sessions:
                logger.debug("Нет активных подключенных сессий для проверки")
                return
            
            # Получаем список активных подключений из MikroTik
            try:
                sessions = get_user_manager_sessions(db)
                # Считаем подключение по активным сессиям из:
                # - User Manager session (флаг A / поле active)
                # - PPP active (это “факт подключения”)
                active_candidates = [
                    s
                    for s in (sessions or [])
                    if (s.get("source") in {"user_manager_session", "ppp_active"})
                    and (bool(s.get("active")) is True)
                ]
                # если по какой-то причине source/active не пришли — fallback на прежнюю эвристику
                candidate = active_candidates if active_candidates else (sessions or [])

                active = []
                for s in candidate:
                    # в "режиме активных" — пропуск неактивных
                    if active_candidates and not (bool(s.get("active")) is True):
                        continue
                    u = s.get("user") or s.get("username") or s.get("name")
                    if not u:
                        continue
                    sid = (
                        s.get("mikrotik_session_id")
                        or s.get(".id")
                        or s.get("id")
                        or s.get("acct-session-id")
                        or s.get("acct_session_id")
                    )
                    active.append((u, sid))
                active_usernames = {u for (u, _sid) in active}
                active_session_id_by_username = {}
                for u, sid in active:
                    if u not in active_session_id_by_username and sid:
                        active_session_id_by_username[u] = sid
            except Exception as e:
                logger.error(f"Ошибка при получении пользователей MikroTik: {e}")
                return

            # Защита от ложных срабатываний: не рвём сессии мгновенно.
            interval_seconds = int(get_setting_value(db, "vpn_connection_check_interval_seconds", 60) or 60)
            disconnect_grace_seconds = max(30, interval_seconds * 2)
            
            # Проверяем каждую сессию
            # (Дополнительно: если MikroTik сообщает активную UM-сессию, а у нас последняя сессия
            # помечена DISCONNECTED — это часто признак ложного отключения. В таком случае
            # "воскрешаем" последнюю сессию для username, чтобы UI отражал реальность.)
            try:
                from sqlalchemy import desc
                for u in list(active_usernames):
                    # есть ли уже отслеживаемая сессия в connected_sessions?
                    if any(s.mikrotik_username == u for s in connected_sessions):
                        continue
                    latest = (
                        db.query(VPNSession)
                        .filter(VPNSession.mikrotik_username == u)
                        .order_by(desc(VPNSession.created_at))
                        .first()
                    )
                    if not latest:
                        continue
                    # воскрешаем только относительно свежие сессии (24 часа)
                    if latest.created_at and (datetime.utcnow() - latest.created_at).total_seconds() > 86400:
                        continue
                    if latest.status == VPNSessionStatus.DISCONNECTED:
                        latest.status = VPNSessionStatus.CONNECTED
                        if not latest.connected_at:
                            latest.connected_at = datetime.utcnow()
                        latest.mikrotik_session_id = active_session_id_by_username.get(u) or latest.mikrotik_session_id
                        latest.last_seen_at = datetime.utcnow()
                        db.commit()
                        connected_sessions.append(latest)
            except Exception:
                db.rollback()

            for session in connected_sessions:
                mikrotik_username = session.mikrotik_username
                
                if mikrotik_username in active_usernames:
                    # Обновляем last_seen_at, чтобы не отключать сессию из-за кратковременных сбоев
                    try:
                        session.last_seen_at = datetime.utcnow()
                        db.commit()
                    except Exception:
                        db.rollback()
                    # Факт подключения обнаружен
                    if session.status == VPNSessionStatus.REQUESTED:
                        # 1) ставим CONNECTED (фиксируем connected_at)
                        connected = mark_session_as_connected(
                            db, session.id, mikrotik_session_id=active_session_id_by_username.get(mikrotik_username)
                        )
                        logger.info(f"Сессия {session.id} отмечена как CONNECTED (подключение обнаружено)")

                        # 2) либо запрашиваем подтверждение, либо подтверждаем автоматически
                        # Пер-пользовательская настройка (если задана) переопределяет глобальную
                        user_settings = None
                        try:
                            from backend.services.user_service import get_user_settings as _get_user_settings
                            user_settings = _get_user_settings(db, session.user_id)
                        except Exception:
                            user_settings = None
                        require_confirmation = (
                            bool(getattr(user_settings, "require_confirmation", global_require_confirmation))
                            if user_settings is not None
                            else global_require_confirmation
                        )

                        if require_confirmation:
                            if NOTIFICATIONS_AVAILABLE:
                                try:
                                    await notify_session_confirmation_required(connected)
                                except Exception as e:
                                    logger.error(f"Ошибка при отправке запроса подтверждения: {e}")
                        else:
                            mark_session_as_confirmed(db, session.id)
                            logger.info(f"Сессия {session.id} подтверждена автоматически (require_confirmation=false)")
                            if NOTIFICATIONS_AVAILABLE:
                                try:
                                    await notify_session_confirmed(session)
                                except Exception as e:
                                    logger.error(f"Ошибка при отправке уведомления о подтверждении: {e}")

                    elif session.status == VPNSessionStatus.CONNECTED:
                        # Пер-пользовательская настройка (если задана) переопределяет глобальную
                        user_settings = None
                        try:
                            from backend.services.user_service import get_user_settings as _get_user_settings
                            user_settings = _get_user_settings(db, session.user_id)
                        except Exception:
                            user_settings = None
                        require_confirmation = (
                            bool(getattr(user_settings, "require_confirmation", global_require_confirmation))
                            if user_settings is not None
                            else global_require_confirmation
                        )

                        if require_confirmation:
                            # ждём ответ пользователя; если превышен таймаут — отключаем
                            if session.connected_at and (datetime.utcnow() - session.connected_at).total_seconds() > confirmation_timeout_seconds:
                                disconnect_vpn_session(db, session.id)
                                logger.info(f"Сессия {session.id} отключена по таймауту подтверждения")
                                if NOTIFICATIONS_AVAILABLE:
                                    try:
                                        await notify_session_disconnected(session)
                                    except Exception as e:
                                        logger.error(f"Ошибка при отправке уведомления об отключении: {e}")
                        else:
                            mark_session_as_confirmed(db, session.id)
                            logger.info(f"Сессия {session.id} подтверждена (auto) при активном подключении")
                else:
                    # Пользователь отключен, но статус еще показывает подключение
                    if session.status in [VPNSessionStatus.CONNECTED, VPNSessionStatus.CONFIRMED, VPNSessionStatus.ACTIVE, VPNSessionStatus.REMINDER_SENT]:
                        now = datetime.utcnow()
                        last_seen = getattr(session, "last_seen_at", None) or session.connected_at

                        # Если видели недавно — ждём grace
                        if last_seen and (now - last_seen).total_seconds() < disconnect_grace_seconds:
                            continue

                        # Отключаем сессию (внутри также выключается firewall и пользователь User Manager)
                        disconnect_vpn_session(db, session.id)
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
                    # (по умолчанию 24 часа, но если есть user_settings.session_duration_hours — используем его)
                    if session.created_at:
                        try:
                            from backend.services.user_service import get_user_settings as _get_user_settings
                            us = _get_user_settings(db, session.user_id)
                            duration_hours = int(getattr(us, "session_duration_hours", 24) or 24) if us else 24
                        except Exception:
                            duration_hours = 24
                        expires_at = session.created_at + timedelta(hours=duration_hours)
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
