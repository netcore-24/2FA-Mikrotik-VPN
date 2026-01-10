#!/bin/bash

# Скрипт запуска приложения MikroTik 2FA VPN System

set -e

# Цвета для вывода
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Функции для вывода
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

log_info "Запуск MikroTik 2FA VPN System..."

# Проверяем наличие виртуального окружения
if [ ! -d "venv" ]; then
    log_error "Виртуальное окружение не найдено. Запустите сначала install.sh"
    exit 1
fi

# Активируем виртуальное окружение
source venv/bin/activate

# Проверяем наличие .env файла
if [ ! -f ".env" ]; then
    log_warn ".env файл не найден. Создайте его на основе .env.example"
    log_warn "cp .env.example .env"
    log_warn "nano .env"
fi

# Создаем необходимые директории
mkdir -p data logs backups

# Проверяем, что приложение установлено
if ! python3 -c "import fastapi" 2>/dev/null; then
    log_error "FastAPI не установлен. Запустите: pip install -r requirements.txt"
    exit 1
fi

# Запускаем приложение
log_info "Запуск FastAPI сервера..."
cd backend

# Используем uvicorn для запуска
exec uvicorn main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --reload \
    --log-level info
