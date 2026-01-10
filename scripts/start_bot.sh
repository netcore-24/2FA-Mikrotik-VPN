#!/bin/bash

# Скрипт запуска Telegram бота

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

log_info "Запуск Telegram бота..."

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

# Проверяем, что TELEGRAM_BOT_TOKEN установлен
if [ -f ".env" ]; then
    export $(grep -v '^#' .env | xargs)
fi

if [ -z "$TELEGRAM_BOT_TOKEN" ]; then
    log_error "TELEGRAM_BOT_TOKEN не установлен в .env файле"
    exit 1
fi

# Проверяем, что приложение установлено
if ! python3 -c "import telegram" 2>/dev/null; then
    log_error "python-telegram-bot не установлен. Запустите: pip install -r requirements.txt"
    exit 1
fi

# Запускаем бота
log_info "Запуск Telegram бота..."
exec python3 -m telegram_bot.bot
