#!/bin/bash

# Скрипт обновления приложения

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

log_info "Обновление MikroTik 2FA VPN System..."

# Проверяем наличие виртуального окружения
if [ ! -d "venv" ]; then
    log_error "Виртуальное окружение не найдено. Запустите сначала install.sh"
    exit 1
fi

# Активируем виртуальное окружение
source venv/bin/activate

# Создаем резервную копию базы данных перед обновлением
log_info "Создание резервной копии базы данных перед обновлением..."
if [ -f "scripts/backup_db.sh" ]; then
    bash scripts/backup_db.sh
else
    log_warn "Скрипт backup_db.sh не найден, резервная копия не создана"
fi

# Обновляем зависимости Python
log_info "Обновление Python зависимостей..."
pip install --upgrade pip
if [ -f "requirements.txt" ]; then
    pip install --upgrade -r requirements.txt
else
    log_warn "Файл requirements.txt не найден"
fi

# Обновляем Frontend зависимости (если требуется)
if [ -d "frontend" ] && [ -f "frontend/package.json" ]; then
    log_info "Обновление Frontend зависимостей..."
    if command -v npm &> /dev/null; then
        cd frontend
        npm install
        npm run build 2>/dev/null || log_warn "Сборка frontend не выполнена (возможно, не настроена)"
        cd ..
    else
        log_warn "npm не обнаружен. Frontend зависимости не обновлены."
    fi
fi

# Выполняем миграции базы данных (если необходимо)
log_info "Проверка миграций базы данных..."
# Миграции выполняются автоматически при запуске приложения

log_info "Обновление завершено успешно!"
log_info ""
log_info "Рекомендуется перезапустить приложение:"
log_info "  ./scripts/start.sh"
log_info ""
log_info "Или через systemd:"
log_info "  sudo systemctl restart mikrotik-2fa-vpn"
