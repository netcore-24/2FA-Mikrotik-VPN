"""
Сервис для управления базой данных (резервное копирование, восстановление, проверка).
"""
import os
import shutil
import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import text
from config.settings import settings
from backend.database import engine
import zipfile
import tarfile


def get_database_info(db: Session) -> Dict[str, Any]:
    """Получить информацию о базе данных."""
    db_path = settings.DATABASE_URL.replace("sqlite:///", "")
    
    if not os.path.exists(db_path):
        return {
            "path": db_path,
            "exists": False,
            "size": 0,
            "size_human": "0 B",
        }
    
    # Получаем размер файла
    size = os.path.getsize(db_path)
    size_human = _format_size(size)
    
    # Получаем версию SQLite
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT sqlite_version()")
    sqlite_version = cursor.fetchone()[0]
    
    # Получаем количество таблиц и записей
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()
    table_counts = {}
    
    for table in tables:
        table_name = table[0]
        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        count = cursor.fetchone()[0]
        table_counts[table_name] = count
    
    conn.close()
    
    # Получаем время последнего изменения
    mtime = os.path.getmtime(db_path)
    last_modified = datetime.fromtimestamp(mtime)
    
    return {
        "path": db_path,
        "exists": True,
        "size": size,
        "size_human": size_human,
        "sqlite_version": sqlite_version,
        "tables": table_counts,
        "total_tables": len(tables),
        "last_modified": last_modified.isoformat(),
    }


def _format_size(size_bytes: int) -> str:
    """Форматировать размер в человекочитаемый формат."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} TB"


def create_backup(
    backup_dir: Optional[str] = None,
    compress: bool = True,
) -> Tuple[str, str]:
    """
    Создать резервную копию базы данных.
    Возвращает (путь к файлу резервной копии, имя файла).
    """
    db_path = settings.DATABASE_URL.replace("sqlite:///", "")
    
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"Database file not found: {db_path}")
    
    # Определяем директорию для резервных копий
    if backup_dir is None:
        backup_dir = getattr(settings, "BACKUP_PATH", "./backups")
    
    # Создаем директорию, если её нет
    os.makedirs(backup_dir, exist_ok=True)
    
    # Формируем имя файла резервной копии
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_filename = f"mikrotik_2fa_backup_{timestamp}.db"
    backup_path = os.path.join(backup_dir, backup_filename)
    
    # Копируем файл базы данных
    shutil.copy2(db_path, backup_path)
    
    # Компрессия, если требуется
    if compress:
        compressed_path = backup_path + ".zip"
        with zipfile.ZipFile(compressed_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            zipf.write(backup_path, backup_filename)
        # Удаляем несжатый файл
        os.remove(backup_path)
        return compressed_path, os.path.basename(compressed_path)
    
    return backup_path, backup_filename


def restore_backup(
    backup_file_path: str,
    create_backup_before_restore: bool = True,
) -> None:
    """
    Восстановить базу данных из резервной копии.
    
    Args:
        backup_file_path: Путь к файлу резервной копии
        create_backup_before_restore: Создать резервную копию текущей БД перед восстановлением
    """
    db_path = settings.DATABASE_URL.replace("sqlite:///", "")
    
    # Создаем резервную копию текущей БД перед восстановлением
    if create_backup_before_restore and os.path.exists(db_path):
        create_backup()
    
    # Определяем, является ли файл архивом
    extracted_path = None
    if backup_file_path.endswith('.zip'):
        # Распаковываем ZIP архив
        backup_dir = os.path.dirname(backup_file_path) or "."
        with zipfile.ZipFile(backup_file_path, 'r') as zipf:
            # Находим .db файл в архиве
            db_files = [f for f in zipf.namelist() if f.endswith('.db')]
            if not db_files:
                raise ValueError("No .db file found in backup archive")
            extracted_file = db_files[0]
            zipf.extract(extracted_file, backup_dir)
            extracted_path = os.path.join(backup_dir, extracted_file)
    elif backup_file_path.endswith('.tar.gz') or backup_file_path.endswith('.tgz'):
        # Распаковываем TAR.GZ архив
        backup_dir = os.path.dirname(backup_file_path) or "."
        with tarfile.open(backup_file_path, 'r:gz') as tarf:
            # Находим .db файл в архиве
            db_files = [f for f in tarf.getnames() if f.endswith('.db')]
            if not db_files:
                raise ValueError("No .db file found in backup archive")
            extracted_file = db_files[0]
            tarf.extract(extracted_file, backup_dir)
            extracted_path = os.path.join(backup_dir, extracted_file)
    else:
        # Обычный .db файл
        extracted_path = backup_file_path
    
    # Проверяем, что файл существует
    if not os.path.exists(extracted_path):
        raise FileNotFoundError(f"Backup file not found: {extracted_path}")
    
    # Валидация: проверяем, что это действительно SQLite база данных
    try:
        conn = sqlite3.connect(extracted_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        conn.close()
        
        if not tables:
            raise ValueError("Backup file does not contain any tables")
    except sqlite3.Error as e:
        raise ValueError(f"Invalid SQLite database file: {str(e)}")
    
    # Копируем файл базы данных
    # Сначала создаем резервную копию текущей БД (если еще не создана)
    if create_backup_before_restore and os.path.exists(db_path):
        # Уже создали выше, но на всякий случай еще раз
        pass
    
    # Убеждаемся, что директория существует
    db_dir = os.path.dirname(db_path)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)
    
    # Копируем файл
    shutil.copy2(extracted_path, db_path)
    
    # Удаляем временный распакованный файл, если это был архив
    if extracted_path != backup_file_path and os.path.exists(extracted_path):
        try:
            os.remove(extracted_path)
        except Exception:
            pass


def verify_database_integrity(db: Session) -> Tuple[bool, Optional[str]]:
    """
    Проверить целостность базы данных SQLite.
    Возвращает (успех, сообщение об ошибке).
    """
    db_path = settings.DATABASE_URL.replace("sqlite:///", "")
    
    if not os.path.exists(db_path):
        return False, "Database file not found"
    
    try:
        # Используем SQLite команду integrity_check
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("PRAGMA integrity_check")
        result = cursor.fetchone()
        conn.close()
        
        if result and result[0] == "ok":
            return True, None
        else:
            return False, result[0] if result else "Unknown integrity check error"
    except Exception as e:
        return False, str(e)


def optimize_database(db: Session) -> Dict[str, Any]:
    """
    Оптимизировать базу данных SQLite (VACUUM, ANALYZE).
    """
    db_path = settings.DATABASE_URL.replace("sqlite:///", "")
    
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"Database file not found: {db_path}")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Получаем размер до оптимизации
        size_before = os.path.getsize(db_path)
        
        # Выполняем VACUUM
        cursor.execute("VACUUM")
        
        # Выполняем ANALYZE для обновления статистики
        cursor.execute("ANALYZE")
        
        conn.commit()
        conn.close()
        
        # Получаем размер после оптимизации
        size_after = os.path.getsize(db_path)
        size_saved = size_before - size_after
        
        return {
            "success": True,
            "size_before": size_before,
            "size_after": size_after,
            "size_saved": size_saved,
            "size_saved_human": _format_size(size_saved),
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }


def get_backup_list(backup_dir: Optional[str] = None) -> list[Dict[str, Any]]:
    """Получить список резервных копий."""
    if backup_dir is None:
        backup_dir = getattr(settings, "BACKUP_PATH", "./backups")
    
    if not os.path.exists(backup_dir):
        return []
    
    backups = []
    for filename in os.listdir(backup_dir):
        if filename.startswith("mikrotik_2fa_backup_") and (filename.endswith(".db") or filename.endswith(".zip") or filename.endswith(".tar.gz")):
            file_path = os.path.join(backup_dir, filename)
            size = os.path.getsize(file_path)
            mtime = os.path.getmtime(file_path)
            
            backups.append({
                "filename": filename,
                "path": file_path,
                "size": size,
                "size_human": _format_size(size),
                "created_at": datetime.fromtimestamp(mtime).isoformat(),
            })
    
    # Сортируем по дате создания (новые первыми)
    backups.sort(key=lambda x: x["created_at"], reverse=True)
    
    return backups
