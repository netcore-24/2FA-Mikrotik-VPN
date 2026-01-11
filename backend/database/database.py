"""
Конфигурация и работа с базой данных SQLite.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
from typing import Generator
import os
from config.settings import settings


# Создание движка базы данных
# Для SQLite используем StaticPool для совместимости с asyncio (если потребуется)
if settings.DATABASE_URL.startswith("sqlite"):
    # Создаем директорию для базы данных, если её нет
    db_path = settings.DATABASE_URL.replace("sqlite:///", "")
    db_dir = os.path.dirname(db_path)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)
    
    engine = create_engine(
        settings.DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=settings.DEBUG,
    )
else:
    engine = create_engine(
        settings.DATABASE_URL,
        echo=settings.DEBUG,
    )

# Создание фабрики сессий
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """
    Генератор для получения сессии базы данных.
    Используется как dependency в FastAPI.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """
    Инициализация базы данных: создание всех таблиц.
    """
    from backend.database.base import Base
    
    # Создаем директорию для базы данных, если её нет
    if settings.DATABASE_URL.startswith("sqlite"):
        db_path = settings.DATABASE_URL.replace("sqlite:///", "")
        db_dir = os.path.dirname(db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)
    
    # Создаем все таблицы
    Base.metadata.create_all(bind=engine)
    # Лёгкая миграция для SQLite (create_all не добавляет новые колонки)
    try:
        if settings.DATABASE_URL.startswith("sqlite"):
            import sqlite3

            db_path = settings.DATABASE_URL.replace("sqlite:///", "")
            con = sqlite3.connect(db_path)
            try:
                cur = con.cursor()
                cols = [r[1] for r in cur.execute("PRAGMA table_info(vpn_sessions);").fetchall()]
                if "mikrotik_session_id" not in cols:
                    cur.execute("ALTER TABLE vpn_sessions ADD COLUMN mikrotik_session_id VARCHAR(64);")
                    con.commit()
                if "last_seen_at" not in cols:
                    cur.execute("ALTER TABLE vpn_sessions ADD COLUMN last_seen_at DATETIME;")
                    con.commit()

                user_setting_cols = [r[1] for r in cur.execute("PRAGMA table_info(user_settings);").fetchall()]
                if "require_confirmation" not in user_setting_cols:
                    cur.execute("ALTER TABLE user_settings ADD COLUMN require_confirmation BOOLEAN NOT NULL DEFAULT 0;")
                    con.commit()
                if "session_duration_hours" not in user_setting_cols:
                    cur.execute("ALTER TABLE user_settings ADD COLUMN session_duration_hours INTEGER NOT NULL DEFAULT 24;")
                    con.commit()

                try:
                    mt_cols = [r[1] for r in cur.execute("PRAGMA table_info(mikrotik_configs);").fetchall()]
                    if "connection_type" in mt_cols:
                        # Нормализация/миграция типов подключения к общим значениям (.value):
                        # ssh_password / ssh_key / api / api_ssl
                        cur.execute("UPDATE mikrotik_configs SET connection_type='ssh_password' WHERE connection_type IN ('SSH_PASSWORD','ssh_password');")
                        cur.execute("UPDATE mikrotik_configs SET connection_type='ssh_key' WHERE connection_type IN ('SSH_KEY','ssh_key');")
                        cur.execute("UPDATE mikrotik_configs SET connection_type='api' WHERE connection_type IN ('API','api','rest_api','routeros_api');")
                        cur.execute("UPDATE mikrotik_configs SET connection_type='api_ssl' WHERE connection_type IN ('API_SSL','api_ssl','api-ssl','routeros_api_ssl');")
                        con.commit()
                except Exception:
                    pass
            finally:
                con.close()
    except Exception:
        # не валим запуск; если не получилось — поле просто будет недоступно до ручной миграции
        pass
    print(f"База данных инициализирована: {settings.DATABASE_URL}")
