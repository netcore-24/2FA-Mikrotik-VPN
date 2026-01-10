"""
API endpoints для управления базой данных.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request, UploadFile, File
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import Optional
import os
import tempfile
from backend.database import get_db
from backend.api.dependencies import get_current_super_admin
from backend.api.i18n_dependencies import get_translate
from backend.api.schemas import (
    DatabaseInfoResponse,
    DatabaseIntegrityResponse,
    DatabaseBackupResponse,
    DatabaseRestoreResponse,
    DatabaseOptimizeResponse,
    BackupListResponse,
)
from backend.services.database_service import (
    get_database_info,
    create_backup,
    restore_backup,
    verify_database_integrity,
    optimize_database,
    get_backup_list,
)
from backend.services.audit_service import create_audit_log
from backend.models.admin import Admin

router = APIRouter(prefix="/database", tags=["database"])


@router.get("/info", response_model=DatabaseInfoResponse)
async def get_database_info_endpoint(
    request: Request,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_super_admin),  # Только супер-администратор
    t=Depends(get_translate),
):
    """
    Получить информацию о базе данных (размер, версия, таблицы).
    Требуются права супер-администратора.
    """
    info = get_database_info(db)
    return DatabaseInfoResponse(**info)


@router.get("/backup")
async def download_backup(
    request: Request,
    compress: bool = True,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_super_admin),  # Только супер-администратор
    t=Depends(get_translate),
):
    """
    Скачать резервную копию базы данных.
    Требуются права супер-администратора.
    """
    try:
        backup_path, backup_filename = create_backup(compress=compress)
        
        # Логируем действие в аудит
        create_audit_log(
            db=db,
            action="database_backup_download",
            admin_id=current_admin.id,
            ip_address=request.client.host if request.client else None,
            details={"backup_filename": backup_filename},
        )
        
        return FileResponse(
            path=backup_path,
            filename=backup_filename,
            media_type="application/octet-stream",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e) or t("error.internal"),
        )


@router.post("/backup", response_model=DatabaseBackupResponse)
async def create_backup_endpoint(
    request: Request,
    compress: bool = True,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_super_admin),  # Только супер-администратор
    t=Depends(get_translate),
):
    """
    Создать резервную копию базы данных (без скачивания).
    Требуются права супер-администратора.
    """
    try:
        backup_path, backup_filename = create_backup(compress=compress)
        
        # Логируем действие в аудит
        create_audit_log(
            db=db,
            action="database_backup_create",
            admin_id=current_admin.id,
            ip_address=request.client.host if request.client else None,
            details={"backup_filename": backup_filename, "backup_path": backup_path},
        )
        
        return DatabaseBackupResponse(
            success=True,
            backup_path=backup_path,
            backup_filename=backup_filename,
            message=t("success.operation"),
        )
    except Exception as e:
        return DatabaseBackupResponse(
            success=False,
            message=str(e) or t("error.internal"),
        )


@router.post("/restore", response_model=DatabaseRestoreResponse)
async def restore_backup_endpoint(
    request: Request,
    file: UploadFile = File(...),
    create_backup: bool = True,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_super_admin),  # Только супер-администратор
    t=Depends(get_translate),
):
    """
    Загрузить и восстановить базу данных из файла резервной копии.
    Требуются права супер-администратора.
    
    Поддерживаемые форматы: .db, .zip, .tar.gz
    """
    # Проверяем расширение файла
    filename = file.filename.lower()
    if not (filename.endswith('.db') or filename.endswith('.zip') or filename.endswith('.tar.gz') or filename.endswith('.tgz')):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=t("validation.invalid_format") + ": Only .db, .zip, .tar.gz files are supported",
        )
    
    # Сохраняем загруженный файл во временную директорию
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(filename)[1]) as tmp_file:
            content = await file.read()
            tmp_file.write(content)
            tmp_path = tmp_file.name
        
        # Восстанавливаем базу данных
        restore_backup(tmp_path, create_backup_before_restore=create_backup)
        
        # Удаляем временный файл
        try:
            os.unlink(tmp_path)
        except Exception:
            pass
        
        # Логируем действие в аудит
        create_audit_log(
            db=db,
            action="database_restore",
            admin_id=current_admin.id,
            ip_address=request.client.host if request.client else None,
            details={"filename": filename, "created_backup_before": create_backup},
        )
        
        return DatabaseRestoreResponse(
            success=True,
            message=t("success.operation"),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        # Удаляем временный файл при ошибке
        try:
            if 'tmp_path' in locals():
                os.unlink(tmp_path)
        except Exception:
            pass
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e) or t("error.internal"),
        )


@router.post("/verify", response_model=DatabaseIntegrityResponse)
async def verify_database_integrity_endpoint(
    request: Request,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_super_admin),  # Только супер-администратор
    t=Depends(get_translate),
):
    """
    Проверить целостность базы данных.
    Требуются права супер-администратора.
    """
    success, error_message = verify_database_integrity(db)
    
    # Логируем действие в аудит
    create_audit_log(
        db=db,
        action="database_verify",
        admin_id=current_admin.id,
        ip_address=request.client.host if request.client else None,
        details={"success": success, "error": error_message},
    )
    
    return DatabaseIntegrityResponse(
        success=success,
        message=error_message,
    )


@router.post("/optimize", response_model=DatabaseOptimizeResponse)
async def optimize_database_endpoint(
    request: Request,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_super_admin),  # Только супер-администратор
    t=Depends(get_translate),
):
    """
    Оптимизировать базу данных (VACUUM, ANALYZE).
    Требуются права супер-администратора.
    """
    try:
        result = optimize_database(db)
        
        # Логируем действие в аудит
        create_audit_log(
            db=db,
            action="database_optimize",
            admin_id=current_admin.id,
            ip_address=request.client.host if request.client else None,
            details=result,
        )
        
        return DatabaseOptimizeResponse(**result)
    except Exception as e:
        return DatabaseOptimizeResponse(
            success=False,
            error=str(e) or t("error.internal"),
        )


@router.get("/backups", response_model=BackupListResponse)
async def list_backups(
    request: Request,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_super_admin),  # Только супер-администратор
    t=Depends(get_translate),
):
    """
    Получить список резервных копий базы данных.
    Требуются права супер-администратора.
    """
    backups = get_backup_list()
    return BackupListResponse(backups=backups)
