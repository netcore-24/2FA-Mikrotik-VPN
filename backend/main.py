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
                        return FileResponse(file_path)
                
                # Возвращаем index.html для SPA роутинга
                index_path = os.path.join(frontend_dist, "index.html")
                if os.path.exists(index_path):
                    return FileResponse(index_path)
                
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
        
        # Запускаем планировщик задач, если не в режиме разработки
        if not settings.DEBUG:
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
