#!/bin/bash

# Скрипт автоматической установки MikroTik 2FA VPN System
# Поддерживает Debian 12-13

set -e

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Функция для вывода сообщений
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Проверка, что скрипт запущен с правами root или sudo
if [ "$EUID" -ne 0 ]; then 
    log_error "Пожалуйста, запустите скрипт с sudo: sudo ./install.sh"
    exit 1
fi

log_info "Начало установки MikroTik 2FA VPN System..."

# Определение версии Debian
if [ -f /etc/debian_version ]; then
    DEBIAN_VERSION=$(cat /etc/debian_version)
    if [[ "$DEBIAN_VERSION" == "12"* ]] || [[ "$DEBIAN_VERSION" == "bookworm"* ]]; then
        log_info "Обнаружена Debian 12 (Bookworm)"
    elif [[ "$DEBIAN_VERSION" == "13"* ]] || [[ "$DEBIAN_VERSION" == "trixie"* ]]; then
        log_info "Обнаружена Debian 13 (Trixie)"
    else
        log_warn "Обнаружена несовместимая версия Debian: $DEBIAN_VERSION"
        log_warn "Рекомендуется Debian 12-13, но установка будет продолжена"
    fi
else
    log_warn "Не удалось определить версию Debian"
    log_warn "Установка будет продолжена, но могут возникнуть проблемы"
fi

# Обновление списка пакетов
log_info "Обновление списка пакетов..."
apt update

# Установка системных пакетов
log_info "Установка системных пакетов..."
apt install -y \
    python3 \
    python3-pip \
    python3-venv \
    python3-dev \
    git \
    curl \
    sqlite3 \
    build-essential \
    libssl-dev \
    libffi-dev

# Проверка наличия Node.js (опционально для frontend)
if ! command -v node &> /dev/null; then
    log_warn "Node.js не обнаружен. Установите его вручную, если требуется сборка frontend:"
    log_warn "curl -fsSL https://deb.nodesource.com/setup_18.x | bash -"
    log_warn "apt install -y nodejs"
else
    log_info "Node.js обнаружен: $(node --version)"
fi

# Создание директорий
log_info "Создание необходимых директорий..."
mkdir -p data
mkdir -p logs
mkdir -p backups

# Настройка прав доступа
log_info "Настройка прав доступа..."
# Получаем пользователя, запустившего скрипт
if [ -n "$SUDO_USER" ]; then
    PROJECT_USER="$SUDO_USER"
else
    PROJECT_USER="root"
fi

# Создание виртуального окружения Python
if [ ! -d "venv" ]; then
    log_info "Создание виртуального окружения Python..."
    python3 -m venv venv
fi

# Активация виртуального окружения и установка зависимостей
log_info "Установка Python зависимостей..."
source venv/bin/activate
pip install --upgrade pip
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt
else
    log_warn "Файл requirements.txt не найден. Пропускаем установку Python зависимостей."
fi
deactivate

# Установка Frontend зависимостей (если требуется)
if [ -d "frontend" ] && [ -f "frontend/package.json" ]; then
    log_info "Установка Frontend зависимостей..."
    if command -v npm &> /dev/null; then
        cd frontend
        npm install
        cd ..
    else
        log_warn "npm не обнаружен. Frontend зависимости не установлены."
    fi
fi

# Настройка прав доступа к файлам
chown -R "$PROJECT_USER:$PROJECT_USER" .
chmod +x scripts/*.sh 2>/dev/null || true

log_info "Установка завершена успешно!"
log_info ""
log_info "Следующие шаги:"
log_info "1. Скопируйте .env.example в .env и настройте переменные окружения:"
log_info "   cp .env.example .env"
log_info "   nano .env"
log_info ""
log_info "2. Создайте первого администратора:"
log_info "   ./scripts/setup_admin.sh"
log_info ""
log_info "3. Запустите приложение:"
log_info "   ./scripts/start.sh"
log_info ""
log_info "Или через systemd (если настроен):"
log_info "   sudo systemctl start mikrotik-2fa-vpn"
