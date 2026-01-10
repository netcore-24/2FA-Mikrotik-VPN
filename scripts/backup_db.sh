#!/bin/bash

# Скрипт резервного копирования базы данных

set -e

# Цвета для вывода
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Определяем корневую директорию проекта
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

# Параметры по умолчанию
BACKUP_DIR="${BACKUP_DIR:-./backups}"
COMPRESS=true

# Парсим аргументы
while [[ $# -gt 0 ]]; do
    case $1 in
        --no-compress)
            COMPRESS=false
            shift
            ;;
        --backup-dir)
            BACKUP_DIR="$2"
            shift 2
            ;;
        *)
            log_error "Неизвестный параметр: $1"
            exit 1
            ;;
    esac
done

log_info "Создание резервной копии базы данных..."

# Проверяем наличие виртуального окружения
if [ ! -d "venv" ]; then
    log_error "Виртуальное окружение не найдено"
    exit 1
fi

# Активируем виртуальное окружение
source venv/bin/activate

# Создаем директорию для резервных копий
mkdir -p "$BACKUP_DIR"

# Загружаем настройки из .env (если есть)
if [ -f ".env" ]; then
    export $(grep -v '^#' .env | xargs)
fi

# Получаем путь к базе данных
DB_PATH="${DATABASE_URL:-sqlite:///./data/mikrotik_2fa.db}"
DB_PATH="${DB_PATH#sqlite:///}"

# Проверяем, что файл базы данных существует
if [ ! -f "$DB_PATH" ]; then
    log_error "Файл базы данных не найден: $DB_PATH"
    exit 1
fi

# Формируем имя файла резервной копии
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILENAME="mikrotik_2fa_backup_${TIMESTAMP}.db"
BACKUP_PATH="${BACKUP_DIR}/${BACKUP_FILENAME}"

log_info "Копирование базы данных..."
cp "$DB_PATH" "$BACKUP_PATH"

if [ "$COMPRESS" = true ]; then
    log_info "Сжатие резервной копии..."
    zip -q "${BACKUP_PATH}.zip" "$BACKUP_PATH"
    rm "$BACKUP_PATH"
    BACKUP_PATH="${BACKUP_PATH}.zip"
    BACKUP_FILENAME="${BACKUP_FILENAME}.zip"
fi

# Получаем размер файла
BACKUP_SIZE=$(du -h "$BACKUP_PATH" | cut -f1)

log_info "Резервная копия создана успешно!"
log_info "  Файл: $BACKUP_PATH"
log_info "  Размер: $BACKUP_SIZE"

# Очистка старых резервных копий (если указан RETENTION_DAYS)
if [ -n "$BACKUP_RETENTION_DAYS" ] && [ "$BACKUP_RETENTION_DAYS" -gt 0 ]; then
    log_info "Очистка резервных копий старше ${BACKUP_RETENTION_DAYS} дней..."
    find "$BACKUP_DIR" -name "mikrotik_2fa_backup_*.db*" -type f -mtime +$BACKUP_RETENTION_DAYS -delete
fi
