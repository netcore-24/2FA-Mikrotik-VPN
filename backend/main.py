"""
Основной файл FastAPI приложения.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import sys
import os

# Добавляем корневую директорию проекта в путь
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import settings
from backend.database import init_db
import uvicorn


def create_app() -> FastAPI:
    """
    Фабрика для создания FastAPI приложения.
    """
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        debug=settings.DEBUG,
    )
    
    # Настройка CORS
    cors_origins = list(settings.CORS_ORIGINS) + ["http://localhost:5173", "http://127.0.0.1:5173"]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Подключение роутеров API (ДО корневых endpoints)
    from backend.api import (
        auth, i18n, users, registration_requests, vpn_sessions,
        settings as settings_api, mikrotik, audit_logs, stats, database, setup_wizard
    )
    app.include_router(auth.router, prefix=settings.API_PREFIX)
    app.include_router(i18n.router, prefix=settings.API_PREFIX)
    app.include_router(users.router, prefix=settings.API_PREFIX)
    app.include_router(registration_requests.router, prefix=settings.API_PREFIX)
    app.include_router(vpn_sessions.router, prefix=settings.API_PREFIX)
    app.include_router(settings_api.router, prefix=settings.API_PREFIX)
    app.include_router(mikrotik.router, prefix=settings.API_PREFIX)
    app.include_router(audit_logs.router, prefix=settings.API_PREFIX)
    app.include_router(stats.router, prefix=settings.API_PREFIX)
    app.include_router(database.router, prefix=settings.API_PREFIX)
    app.include_router(setup_wizard.router, prefix=settings.API_PREFIX)
    
    # API endpoints для информации
    @app.get("/api/info")
    async def api_info():
        return {
            "name": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "status": "running"
        }
    
    # Health check endpoint
    @app.get("/health")
    async def health_check():
        return {"status": "healthy"}
    
    # Проверяем наличие собранного фронтенда
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    frontend_dist = os.path.join(project_root, "frontend", "dist")
    has_frontend = os.path.exists(frontend_dist) and os.path.exists(os.path.join(frontend_dist, "index.html"))
    
    if has_frontend:
        # Статические файлы для фронтенда (в продакшене)
        try:
            from fastapi.staticfiles import StaticFiles
            from fastapi.responses import FileResponse
            
            # Статические ресурсы (JS, CSS, images)
            assets_dir = os.path.join(frontend_dist, "assets")
            if os.path.exists(assets_dir):
                app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")
            
            # Обслуживание index.html для всех не-API путей (catch-all)
            @app.get("/{full_path:path}")
            async def serve_frontend(full_path: str):
                """Обслуживать фронтенд для всех не-API путей."""
                # Игнорируем API и служебные пути
                if (full_path.startswith("api") or 
                    full_path.startswith("docs") or 
                    full_path.startswith("redoc") or 
                    full_path.startswith("openapi.json") or
                    full_path == "health"):
                    return {"error": "Not found"}
                
                # Проверяем существование файла
                if full_path:
                    file_path = os.path.join(frontend_dist, full_path)
                    if os.path.exists(file_path) and os.path.isfile(file_path):
                        # Важно: не кэшируем HTML/SPA-страницы, иначе после обновлений может оставаться старый UI
                        return FileResponse(file_path, headers={"Cache-Control": "no-store"})
                
                # Возвращаем index.html для SPA роутинга
                index_path = os.path.join(frontend_dist, "index.html")
                if os.path.exists(index_path):
                    # Важно: index.html всегда no-store, чтобы новый bundle подхватывался сразу
                    return FileResponse(index_path, headers={"Cache-Control": "no-store"})
                
                return {"error": "Frontend not found"}
        except Exception as e:
            # Если ошибка при настройке статики, используем корневой endpoint
            has_frontend = False
    
    if not has_frontend:
        # Если фронтенд не собран, возвращаем JSON для корневого пути
        @app.get("/")
        async def root():
            return {
                "name": settings.APP_NAME,
                "version": settings.APP_VERSION,
                "status": "running",
                "frontend": "not built - run 'cd frontend && npm run build'",
            }
    
    # Инициализация базы данных при старте
    @app.on_event("startup")
    async def startup_event():
        init_db()
        
        # Синхронизируем настройки из БД в .env файл при старте
        # Это позволяет применять настройки, сделанные через веб-интерфейс
        try:
            from config.settings import load_settings_from_db
            load_settings_from_db()
        except Exception as e:
            # Не критичная ошибка - продолжаем работу
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Не удалось загрузить настройки из БД при старте: {e}")
        
        # Обеспечиваем наличие базовых VPN-настроек (чтобы их было видно в UI)
        try:
            from backend.database import SessionLocal
            from backend.services.settings_service import get_setting_by_key, set_setting
            db = SessionLocal()
            try:
                defaults = [
                    ("vpn_require_confirmation", False, "vpn", "Требовать подтверждение 'Это вы подключились?' перед включением firewall"),
                    ("vpn_confirmation_timeout_seconds", 300, "vpn", "Таймаут ожидания подтверждения (сек)"),
                    # Важно: влияет на задержку появления 2FA-запроса после фактического подключения.
                    ("vpn_connection_check_interval_seconds", 3, "vpn", "Интервал проверки активных подключений (сек)"),
                ]
                for key, value, category, desc in defaults:
                    if not get_setting_by_key(db, key):
                        set_setting(db, key=key, value=value, category=category, description=desc, is_encrypted=False)

                # Шаблоны сообщений Telegram (можно редактировать в UI, категория: telegram_templates)
                telegram_defaults = [
                    (
                        "telegram_template_confirmation_required",
                        "❓ Обнаружено подключение к VPN.\n\n"
                        "Это вы подключились?\n"
                        "Пользователь: {full_name}\n"
                        "MikroTik user: {mikrotik_username}\n"
                        "MikroTik session id: {mikrotik_session_id}\n\n"
                        "Подтвердите, чтобы открыть доступ (включить правило firewall).",
                        "telegram_templates",
                        "Шаблон: запрос подтверждения подключения (2FA). Доступные плейсхолдеры: {full_name}, {telegram_id}, {mikrotik_username}, {mikrotik_session_id}, {expires_at}, {now}.",
                    ),
                    (
                        "telegram_template_session_confirmed",
                        "✅ Подключение подтверждено.\n"
                        "Сессия: {mikrotik_session_id}\n"
                        "Доступ до: {expires_at}",
                        "telegram_templates",
                        "Шаблон: подтверждение сессии. Плейсхолдеры: {full_name}, {mikrotik_username}, {mikrotik_session_id}, {expires_at}, {now}.",
                    ),
                    (
                        "telegram_template_session_disconnected",
                        "❌ Доступ к VPN отключен.\n"
                        "MikroTik user: {mikrotik_username}\n"
                        "Сессия: {mikrotik_session_id}",
                        "telegram_templates",
                        "Шаблон: отключение сессии. Плейсхолдеры: {full_name}, {mikrotik_username}, {mikrotik_session_id}, {now}.",
                    ),
                    (
                        "telegram_template_session_expired",
                        "⌛️ Время VPN-сессии истекло.\n"
                        "MikroTik user: {mikrotik_username}\n"
                        "Сессия: {mikrotik_session_id}",
                        "telegram_templates",
                        "Шаблон: истечение сессии. Плейсхолдеры: {full_name}, {mikrotik_username}, {mikrotik_session_id}, {expires_at}, {now}.",
                    ),
                    (
                        "telegram_template_session_reminder",
                        "⏰ Напоминание: VPN-сессия скоро истечет.\n"
                        "Осталось часов: {hours_remaining}\n"
                        "Доступ до: {expires_at}\n"
                        "MikroTik user: {mikrotik_username}",
                        "telegram_templates",
                        "Шаблон: напоминание. Плейсхолдеры: {full_name}, {mikrotik_username}, {mikrotik_session_id}, {expires_at}, {hours_remaining}, {now}.",
                    ),
                ]
                for key, value, category, desc in telegram_defaults:
                    existing = get_setting_by_key(db, key)
                    if not existing:
                        set_setting(db, key=key, value=value, category=category, description=desc, is_encrypted=False)
                    else:
                        # Миграция: раньше шаблоны жили в category=telegram → переносим в telegram_templates
                        if existing.category != category:
                            existing.category = category
                            db.commit()
            finally:
                db.close()
        except Exception:
            pass

        # Запускаем планировщик задач (по умолчанию включен и в prod, и в dev).
        # В dev-среде можно отключить через DISABLE_SCHEDULER=1.
        if os.environ.get("DISABLE_SCHEDULER") != "1":
            from backend.services.scheduler_service import scheduler_service
            scheduler_service.start()
    
    @app.on_event("shutdown")
    async def shutdown_event():
        # Останавливаем планировщик задач
        from backend.services.scheduler_service import scheduler_service
        scheduler_service.stop()
    
    return app


# Создание приложения
app = create_app()


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
    )
