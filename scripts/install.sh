#!/bin/bash

# Скрипт автоматической установки MikroTik 2FA VPN System
# Этот скрипт скачивает проект из git репозитория и полностью автоматизирует установку

set -e

# Цвета для вывода
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
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

log_step() {
    echo -e "${BLUE}[STEP]${NC} $1"
}

# Параметры установки
INSTALL_DIR="${INSTALL_DIR:-/opt/mikrotik-2fa-vpn}"
GIT_REPO="${GIT_REPO:-}"  # Будет передан пользователем или через переменную окружения
GIT_BRANCH="${GIT_BRANCH:-main}"
SYSTEM_USER="${SYSTEM_USER:-mikrotik-2fa}"
CREATE_SYSTEMD_SERVICE="${CREATE_SYSTEMD_SERVICE:-true}"
CREATE_SYMLINK="${CREATE_SYMLINK:-false}"

# Проверка прав root
if [ "$EUID" -ne 0 ]; then 
    log_error "Этот скрипт должен быть запущен с правами root (sudo)"
    exit 1
fi

log_info "=========================================="
log_info "  MikroTik 2FA VPN System - Установка"
log_info "=========================================="
echo ""

# Шаг 1: Проверка зависимостей системы
log_step "Шаг 1: Проверка системных зависимостей..."

# Проверяем наличие Python 3
if ! command -v python3 &> /dev/null; then
    log_error "Python 3 не установлен. Установите Python 3.8 или выше."
    exit 1
fi

PYTHON_VERSION=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1,2)
if [ "$(printf '%s\n' "3.8" "$PYTHON_VERSION" | sort -V | head -n1)" != "3.8" ]; then
    log_error "Требуется Python 3.8 или выше. Установлен: $PYTHON_VERSION"
    exit 1
fi

log_info "✓ Python $PYTHON_VERSION найден"

# Проверяем наличие git
if ! command -v git &> /dev/null; then
    log_warn "Git не установлен. Устанавливаю..."
    if command -v apt-get &> /dev/null; then
        apt-get update && apt-get install -y git
    elif command -v yum &> /dev/null; then
        yum install -y git
    else
        log_error "Не удалось определить менеджер пакетов. Установите git вручную."
        exit 1
    fi
fi

log_info "✓ Git установлен"

# Проверяем наличие pip
if ! command -v pip3 &> /dev/null; then
    log_warn "pip3 не установлен. Устанавливаю..."
    if command -v apt-get &> /dev/null; then
        apt-get install -y python3-pip
    elif command -v yum &> /dev/null; then
        yum install -y python3-pip
    fi
fi

log_info "✓ pip3 установлен"
echo ""

# Шаг 2: Запрос URL репозитория
log_step "Шаг 2: Настройка репозитория..."

if [ -z "$GIT_REPO" ]; then
    echo ""
    read -p "Введите URL git репозитория (или нажмите Enter для использования значения по умолчанию): " GIT_REPO_INPUT
    if [ -n "$GIT_REPO_INPUT" ]; then
        GIT_REPO="$GIT_REPO_INPUT"
    fi
fi

if [ -z "$GIT_REPO" ]; then
    log_error "URL репозитория не указан. Используйте переменную окружения GIT_REPO или укажите при запуске."
    exit 1
fi

log_info "Репозиторий: $GIT_REPO"
log_info "Ветка: $GIT_BRANCH"
log_info "Директория установки: $INSTALL_DIR"
echo ""

# Шаг 3: Создание системного пользователя
log_step "Шаг 3: Создание системного пользователя..."

if ! id "$SYSTEM_USER" &>/dev/null; then
    useradd -r -s /bin/false -d "$INSTALL_DIR" "$SYSTEM_USER"
    log_info "✓ Пользователь $SYSTEM_USER создан"
else
    log_info "✓ Пользователь $SYSTEM_USER уже существует"
fi

# Шаг 4: Клонирование или обновление репозитория
log_step "Шаг 4: Клонирование репозитория..."

if [ -d "$INSTALL_DIR" ]; then
    log_warn "Директория $INSTALL_DIR уже существует"
    read -p "Обновить существующую установку? (y/N): " UPDATE_EXISTING
    if [[ "$UPDATE_EXISTING" =~ ^[Yy]$ ]]; then
        log_info "Обновление существующей установки..."
        cd "$INSTALL_DIR"
        git fetch origin
        git reset --hard "origin/$GIT_BRANCH"
        git clean -fd
    else
        log_error "Установка отменена"
        exit 1
    fi
else
    log_info "Клонирование репозитория..."
    mkdir -p "$(dirname "$INSTALL_DIR")"
    git clone -b "$GIT_BRANCH" "$GIT_REPO" "$INSTALL_DIR"
fi

log_info "✓ Репозиторий готов"
echo ""

# Шаг 5: Установка Python зависимостей
log_step "Шаг 5: Установка Python зависимостей..."

cd "$INSTALL_DIR"

# Создаем виртуальное окружение
if [ ! -d "venv" ]; then
    log_info "Создание виртуального окружения..."
    python3 -m venv venv
fi

log_info "Активация виртуального окружения..."
source venv/bin/activate

log_info "Обновление pip..."
pip install --upgrade pip setuptools wheel

if [ -f "requirements.txt" ]; then
    log_info "Установка зависимостей из requirements.txt..."
    pip install -r requirements.txt
    log_info "✓ Зависимости установлены"
else
    log_error "Файл requirements.txt не найден"
    exit 1
fi

echo ""

# Шаг 5.5: Установка Frontend зависимостей (опционально)
log_step "Шаг 5.5: Установка Frontend зависимостей..."

if [ -d "frontend" ] && command -v npm &> /dev/null; then
    log_info "Установка npm зависимостей..."
    cd "$INSTALL_DIR/frontend"
    npm install
    log_info "✓ Frontend зависимости установлены"
    cd "$INSTALL_DIR"
else
    log_warn "npm не найден или директория frontend отсутствует. Frontend не будет установлен."
fi

echo ""

# Шаг 6: Настройка конфигурации
log_step "Шаг 6: Настройка конфигурации..."

if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        log_info "Создание .env файла из примера..."
        cp .env.example .env
        
        # Генерируем секретные ключи
        SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
        JWT_SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
        
        # Заменяем значения в .env
        sed -i "s|SECRET_KEY=.*|SECRET_KEY=$SECRET_KEY|g" .env
        sed -i "s|JWT_SECRET_KEY=.*|JWT_SECRET_KEY=$JWT_SECRET_KEY|g" .env
        
        log_warn "✓ Файл .env создан. Пожалуйста, отредактируйте его и укажите необходимые параметры:"
        log_warn "  nano $INSTALL_DIR/.env"
    else
        log_error "Файл .env.example не найден"
    fi
else
    log_info "✓ Файл .env уже существует"
fi

echo ""

# Шаг 7: Создание необходимых директорий
log_step "Шаг 7: Создание директорий..."

mkdir -p "$INSTALL_DIR/data"
mkdir -p "$INSTALL_DIR/logs"
mkdir -p "$INSTALL_DIR/backups"

log_info "✓ Директории созданы"
echo ""

# Шаг 8: Инициализация базы данных
log_step "Шаг 8: Инициализация базы данных..."

log_info "Инициализация БД..."
python3 -c "
import sys
sys.path.insert(0, '$INSTALL_DIR')
from backend.database import init_db
init_db()
print('База данных инициализирована')
"

log_info "✓ База данных готова"
echo ""

# Шаг 9: Установка прав доступа
log_step "Шаг 9: Установка прав доступа..."

chown -R "$SYSTEM_USER:$SYSTEM_USER" "$INSTALL_DIR"
chmod +x "$INSTALL_DIR/scripts"/*.sh 2>/dev/null || true

log_info "✓ Права доступа установлены"
echo ""

# Шаг 10: Создание systemd service
if [ "$CREATE_SYSTEMD_SERVICE" = "true" ]; then
    log_step "Шаг 10: Создание systemd service..."
    
    SERVICE_FILE="/etc/systemd/system/mikrotik-2fa-vpn.service"
    
    # Обновляем путь в service файле
    sed "s|/opt/mikrotik-2fa-vpn|$INSTALL_DIR|g" "$INSTALL_DIR/mikrotik-2fa-vpn.service" > "$SERVICE_FILE"
    sed -i "s|User=root|User=$SYSTEM_USER|g" "$SERVICE_FILE"
    
    systemctl daemon-reload
    systemctl enable mikrotik-2fa-vpn.service
    
    log_info "✓ Systemd service создан и включен"
    echo ""
fi

# Шаг 11: Создание симлинка (опционально)
if [ "$CREATE_SYMLINK" = "true" ]; then
    log_step "Шаг 11: Создание симлинка..."
    
    SYMLINK_PATH="/usr/local/bin/mikrotik-2fa-vpn"
    if [ ! -L "$SYMLINK_PATH" ]; then
        ln -s "$INSTALL_DIR/scripts/start.sh" "$SYMLINK_PATH"
        log_info "✓ Симлинк создан: $SYMLINK_PATH"
    fi
    echo ""
fi

# Итоговая информация
log_info "=========================================="
log_info "  Установка завершена успешно!"
log_info "=========================================="
echo ""
log_info "Следующие шаги:"
echo ""
log_info "1. Настройте конфигурацию:"
log_info "   nano $INSTALL_DIR/.env"
echo ""
log_info "2. Создайте первого администратора:"
log_info "   sudo -u $SYSTEM_USER $INSTALL_DIR/scripts/setup_admin.sh"
echo ""
log_info "3. Запустите сервис:"
if [ "$CREATE_SYSTEMD_SERVICE" = "true" ]; then
    log_info "   sudo systemctl start mikrotik-2fa-vpn"
    log_info "   sudo systemctl status mikrotik-2fa-vpn"
else
    log_info "   $INSTALL_DIR/scripts/start.sh"
fi
echo ""
log_info "4. Запустите Telegram бота (в отдельном процессе):"
log_info "   sudo -u $SYSTEM_USER $INSTALL_DIR/scripts/start_bot.sh"
echo ""
log_info "Документация: $INSTALL_DIR/README.md"
echo ""
log_warn "ВАЖНО: Не забудьте настроить .env файл перед запуском!"
