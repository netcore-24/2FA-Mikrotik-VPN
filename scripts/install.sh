#!/bin/bash

# Скрипт автоматической установки MikroTik 2FA VPN System
# Полностью автоматизирует установку, сборку, запуск и настройку автозагрузки

set -e

# Цвета для вывода
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
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

log_success() {
    echo -e "${CYAN}[✓]${NC} $1"
}

# Параметры установки
INSTALL_DIR="${INSTALL_DIR:-/opt/mikrotik-2fa-vpn}"
GIT_REPO="${GIT_REPO:-}"
GIT_BRANCH="${GIT_BRANCH:-main}"
SYSTEM_USER="${SYSTEM_USER:-mikrotik-2fa}"
CREATE_SYSTEMD_SERVICE="${CREATE_SYSTEMD_SERVICE:-true}"
AUTO_START="${AUTO_START:-true}"
CREATE_ADMIN="${CREATE_ADMIN:-true}"
NON_INTERACTIVE="${NON_INTERACTIVE:-false}"

# Проверка прав root
if [ "$EUID" -ne 0 ]; then 
    log_error "Этот скрипт должен быть запущен с правами root (sudo)"
    exit 1
fi

log_info "=========================================="
log_info "  MikroTik 2FA VPN System - Установка"
log_info "=========================================="
echo ""

# Функция проверки команды
check_command() {
    if command -v "$1" &> /dev/null; then
        return 0
    fi
    return 1
}

# Функция проверки установки пакета (для Debian/Ubuntu)
check_package() {
    if check_command dpkg; then
        dpkg -l | grep -q "^ii.*$1" 2>/dev/null
    elif check_command rpm; then
        rpm -q "$1" &>/dev/null
    else
        return 1
    fi
}

# ============================================
# ШАГ 1: Проверка системных зависимостей
# ============================================
log_step "Шаг 1: Проверка и установка системных зависимостей..."

# Проверяем наличие Python 3
if ! check_command python3; then
    log_error "Python 3 не установлен. Устанавливаю..."
    if check_command apt-get; then
        apt-get update -qq && apt-get install -y python3 python3-dev
    elif check_command yum; then
        yum install -y python3 python3-devel
    else
        log_error "Не удалось определить менеджер пакетов"
        exit 1
    fi
fi

PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
PYTHON_MAJOR_MINOR=$(echo "$PYTHON_VERSION" | cut -d'.' -f1,2)
if [ "$(printf '%s\n' "3.8" "$PYTHON_MAJOR_MINOR" | sort -V | head -n1)" != "3.8" ]; then
    log_error "Требуется Python 3.8 или выше. Установлен: $PYTHON_VERSION"
    exit 1
fi
log_success "Python $PYTHON_VERSION найден"

# Устанавливаем системные пакеты
log_info "Установка системных пакетов..."
if check_command apt-get; then
    apt-get update -qq
    DEBIAN_FRONTEND=noninteractive apt-get install -y \
        python3-venv python3-pip python3-dev git curl build-essential \
        libssl-dev libffi-dev 2>&1 | grep -v "^$" | tail -5 || true
    
    # Устанавливаем Rust и Cargo если не установлены
    if ! check_command rustc; then
        log_info "Установка Rust для сборки нативных модулей..."
        DEBIAN_FRONTEND=noninteractive apt-get install -y rustc cargo 2>&1 | tail -3 || true
    fi
elif check_command yum; then
    yum install -y python3 python3-pip python3-devel git curl gcc gcc-c++ \
        openssl-devel libffi-devel 2>&1 | tail -5 || true
    
    if ! check_command rustc; then
        log_info "Установка Rust для сборки нативных модулей..."
        yum install -y rust cargo 2>&1 | tail -3 || true
    fi
else
    log_error "Не удалось определить менеджер пакетов (apt-get/yum)"
    exit 1
fi

log_success "Системные пакеты установлены"

# Устанавливаем Node.js если не установлен
if ! check_command node; then
    log_info "Установка Node.js..."
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - 2>&1 | grep -v "^$" | tail -3 || true
    if check_command apt-get; then
        DEBIAN_FRONTEND=noninteractive apt-get install -y nodejs 2>&1 | tail -3 || true
    elif check_command yum; then
        yum install -y nodejs 2>&1 | tail -3 || true
    fi
fi

if check_command node && check_command npm; then
    NODE_VERSION=$(node --version)
    NPM_VERSION=$(npm --version)
    log_success "Node.js $NODE_VERSION и npm $NPM_VERSION установлены"
else
    log_error "Не удалось установить Node.js и npm"
    exit 1
fi

echo ""

# ============================================
# ШАГ 2: Определение источника проекта
# ============================================
log_step "Шаг 2: Определение источника проекта..."

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CURRENT_DIR="$(pwd)"

# Проверяем, есть ли проект в текущей директории или рядом со скриптом
if [ -f "$CURRENT_DIR/requirements.txt" ] && [ -f "$CURRENT_DIR/backend/main.py" ]; then
    log_info "Используется локальный проект из: $CURRENT_DIR"
    PROJECT_DIR="$CURRENT_DIR"
    USE_GIT=false
elif [ -f "$SCRIPT_DIR/../requirements.txt" ] && [ -f "$SCRIPT_DIR/../backend/main.py" ]; then
    log_info "Используется локальный проект из: $(cd "$SCRIPT_DIR/.." && pwd)"
    PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
    USE_GIT=false
elif [ -n "$GIT_REPO" ]; then
    log_info "Используется git репозиторий: $GIT_REPO"
    USE_GIT=true
else
    log_error "Не найден проект. Варианты:"
    log_error "  1. Укажите GIT_REPO для клонирования: GIT_REPO=url sudo bash install.sh"
    log_error "  2. Запустите скрипт из директории проекта"
    exit 1
fi

if [ "$USE_GIT" = true ]; then
    # Клонирование репозитория
    log_step "Шаг 3: Клонирование репозитория..."
    
    if [ -d "$INSTALL_DIR" ]; then
        log_warn "Директория $INSTALL_DIR уже существует"
        if [ "$NON_INTERACTIVE" != "true" ]; then
            read -p "Удалить и пересоздать? (y/N): " -n 1 -r
            echo
            if [[ $REPLY =~ ^[Yy]$ ]]; then
                log_info "Удаление существующей директории..."
                rm -rf "$INSTALL_DIR"
            else
                log_info "Используется существующая директория"
            fi
        else
            log_info "NON_INTERACTIVE=true, используем существующую директорию"
        fi
    fi
    
    if [ ! -d "$INSTALL_DIR" ]; then
        log_info "Клонирование репозитория $GIT_REPO (ветка: $GIT_BRANCH)..."
        git clone -b "$GIT_BRANCH" "$GIT_REPO" "$INSTALL_DIR" || {
            log_error "Ошибка клонирования репозитория"
            exit 1
        }
        log_success "Репозиторий склонирован в $INSTALL_DIR"
    fi
    
    PROJECT_DIR="$INSTALL_DIR"
else
    log_info "Рабочая директория: $PROJECT_DIR"
fi

cd "$PROJECT_DIR" || {
    log_error "Не удалось перейти в директорию проекта: $PROJECT_DIR"
    exit 1
}

# ============================================
# ШАГ 3: Создание системного пользователя
# ============================================
log_step "Шаг 3: Создание системного пользователя..."

if [ "$USE_GIT" = true ]; then
    if id "$SYSTEM_USER" &>/dev/null; then
        log_info "Пользователь $SYSTEM_USER уже существует"
    else
        log_info "Создание системного пользователя $SYSTEM_USER..."
        useradd -r -s /bin/bash -d "$PROJECT_DIR" -m "$SYSTEM_USER" 2>/dev/null || {
            log_warn "Не удалось создать пользователя $SYSTEM_USER"
            log_warn "Продолжаем с текущим пользователем: $(whoami)"
            SYSTEM_USER=$(whoami)
        }
    fi
    if id "$SYSTEM_USER" &>/dev/null; then
        log_success "Пользователь $SYSTEM_USER готов к использованию"
    else
        SYSTEM_USER=$(whoami)
        log_info "Используется текущий пользователь: $SYSTEM_USER"
    fi
else
    # Для локальной установки используем текущего пользователя
    SYSTEM_USER="${SYSTEM_USER:-$(whoami)}"
    log_info "Локальная установка, используется пользователь: $SYSTEM_USER"
fi

# ============================================
# ШАГ 4: Создание виртуального окружения
# ============================================
log_step "Шаг 4: Создание виртуального окружения Python..."

if [ ! -d "venv" ]; then
    log_info "Создание виртуального окружения..."
    python3 -m venv venv || {
        log_error "Ошибка создания виртуального окружения"
        exit 1
    }
    log_success "Виртуальное окружение создано"
else
    log_info "Виртуальное окружение уже существует"
fi

# Активируем виртуальное окружение
source venv/bin/activate || {
    log_error "Ошибка активации виртуального окружения"
    exit 1
}

# Обновляем pip
log_info "Обновление pip, setuptools, wheel..."
pip install --upgrade pip setuptools wheel -q || {
    log_error "Ошибка обновления pip"
    exit 1
}

# ============================================
# ШАГ 5: Установка Python зависимостей
# ============================================
log_step "Шаг 5: Установка Python зависимостей..."

if [ -f "requirements.txt" ]; then
    log_info "Установка зависимостей из requirements.txt (это может занять несколько минут)..."
    
    # Устанавливаем сначала bcrypt совместимую версию
    pip install 'bcrypt<5.0.0' 'passlib[bcrypt]' email-validator -q
    
    # Устанавливаем остальные зависимости
    pip install -r requirements.txt -q 2>&1 | grep -E "(ERROR|Successfully installed|Requirement already satisfied)" | tail -10 || {
        log_warn "Некоторые зависимости могли не установиться, но продолжаем..."
    }
    
    log_success "Python зависимости установлены"
else
    log_error "Файл requirements.txt не найден в $PROJECT_DIR"
    exit 1
fi

# ============================================
# ШАГ 6: Настройка конфигурации
# ============================================
log_step "Шаг 6: Настройка конфигурации..."

if [ ! -f ".env" ]; then
    log_info "Создание .env файла..."
    if [ -f ".env.example" ]; then
        cp .env.example .env
    else
        # Создаем базовый .env файл
        cat > .env << 'ENVEOF'
# Основные настройки приложения
APP_NAME=MikroTik 2FA VPN System
APP_VERSION=1.0.0
DEBUG=False
LANGUAGE=ru

# База данных
DATABASE_URL=sqlite:///./data/database.db

# JWT токены
SECRET_KEY=
JWT_SECRET_KEY=
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7

# CORS
CORS_ORIGINS=["http://localhost:3000","http://localhost:5173","http://localhost:8000"]

# Telegram Bot
TELEGRAM_BOT_TOKEN=

# MikroTik
MIKROTIK_HOST=
MIKROTIK_PORT=8728
MIKROTIK_USERNAME=
MIKROTIK_PASSWORD=
MIKROTIK_USE_SSL=False

# Пути
BACKUP_PATH=./data/backups

# Шифрование
ENCRYPTION_KEY=
ENVEOF
    fi
    
    # Генерируем ключи
    log_info "Генерация секретных ключей..."
    SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))" 2>/dev/null || echo "")
    ENCRYPTION_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())" 2>/dev/null || echo "")
    
    if [ -z "$SECRET_KEY" ] || [ -z "$ENCRYPTION_KEY" ]; then
        log_error "Ошибка генерации ключей"
        exit 1
    fi
    
    # Обновляем .env файл
    if grep -q "^SECRET_KEY=" .env 2>/dev/null; then
        sed -i "s|^SECRET_KEY=.*|SECRET_KEY=$SECRET_KEY|g" .env
    else
        echo "SECRET_KEY=$SECRET_KEY" >> .env
    fi
    
    if grep -q "^JWT_SECRET_KEY=" .env 2>/dev/null; then
        sed -i "s|^JWT_SECRET_KEY=.*|JWT_SECRET_KEY=$SECRET_KEY|g" .env
    else
        echo "JWT_SECRET_KEY=$SECRET_KEY" >> .env
    fi
    
    if grep -q "^ENCRYPTION_KEY=" .env 2>/dev/null; then
        sed -i "s|^ENCRYPTION_KEY=.*|ENCRYPTION_KEY=$ENCRYPTION_KEY|g" .env
    else
        echo "ENCRYPTION_KEY=$ENCRYPTION_KEY" >> .env
    fi
    
    log_success ".env файл создан и настроен"
else
    log_info ".env файл уже существует, пропускаем создание"
fi

# ============================================
# ШАГ 7: Создание директорий
# ============================================
log_step "Шаг 7: Создание необходимых директорий..."

mkdir -p data data/backups logs frontend/dist
log_success "Директории созданы"

# ============================================
# ШАГ 8: Инициализация базы данных
# ============================================
log_step "Шаг 8: Инициализация базы данных..."

DB_INIT_OUTPUT=$(python3 -c "from backend.database import init_db; init_db(); print('✓ База данных инициализирована')" 2>&1 | grep -v "trapped" | grep -v "^$" || true)

if echo "$DB_INIT_OUTPUT" | grep -q "инициализирована\|initialized"; then
    log_success "База данных инициализирована"
elif [ -f "data/database.db" ]; then
    log_info "База данных уже существует"
else
    log_error "Ошибка инициализации базы данных"
    echo "$DB_INIT_OUTPUT"
    exit 1
fi

# ============================================
# ШАГ 9: Создание администратора
# ============================================
log_step "Шаг 9: Создание администратора..."

if [ "$CREATE_ADMIN" = "true" ]; then
    ADMIN_USERNAME="${ADMIN_USERNAME:-admin}"
    ADMIN_EMAIL="${ADMIN_EMAIL:-admin@example.com}"
    ADMIN_PASSWORD="${ADMIN_PASSWORD:-}"
    
    if [ -z "$ADMIN_PASSWORD" ]; then
        # Генерируем случайный пароль
        ADMIN_PASSWORD=$(python3 -c "import secrets; print(secrets.token_urlsafe(9)[:12])" 2>/dev/null || \
            openssl rand -base64 12 | tr -d "=+/" | cut -c1-12 2>/dev/null || \
            echo "admin$(date +%s | tail -c 5)")
        log_info "Пароль администратора сгенерирован автоматически"
    fi
    
    # Экспортируем переменные для Python скрипта
    export ADMIN_USERNAME ADMIN_EMAIL ADMIN_PASSWORD
    
    ADMIN_CREATE_OUTPUT=$(python3 << 'PYTHON_SCRIPT'
import sys
import os
sys.path.insert(0, os.getcwd())

try:
    from backend.database import SessionLocal
    from backend.services.auth_service import create_admin, get_admin_by_username
    
    db = SessionLocal()
    try:
        admin_username = os.environ.get('ADMIN_USERNAME', 'admin')
        admin_email = os.environ.get('ADMIN_EMAIL', 'admin@example.com')
        admin_password = os.environ.get('ADMIN_PASSWORD', '')
        
        existing = get_admin_by_username(db, admin_username)
        if existing:
            print(f"EXISTS: {existing.username}")
            sys.exit(0)
        else:
            admin = create_admin(
                db=db,
                username=admin_username,
                email=admin_email,
                password=admin_password,
                full_name="System Administrator",
                is_super_admin=True
            )
            print(f"CREATED: {admin.username}")
            print(f"EMAIL: {admin.email}")
            print(f"PASSWORD: {admin_password}")
            sys.exit(0)
    except Exception as e:
        print(f"ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        db.close()
except Exception as e:
    print(f"IMPORT_ERROR: {str(e)}")
    sys.exit(1)
PYTHON_SCRIPT
    )
    
    ADMIN_CREATE_EXIT_CODE=$?
    
    if [ $ADMIN_CREATE_EXIT_CODE -eq 0 ]; then
        if echo "$ADMIN_CREATE_OUTPUT" | grep -q "EXISTS:"; then
            EXISTING_USERNAME=$(echo "$ADMIN_CREATE_OUTPUT" | grep "EXISTS:" | cut -d' ' -f2)
            log_info "Администратор уже существует: $EXISTING_USERNAME"
            ADMIN_CREDENTIALS="Администратор уже существует: $EXISTING_USERNAME"
        elif echo "$ADMIN_CREATE_OUTPUT" | grep -q "CREATED:"; then
            CREATED_USERNAME=$(echo "$ADMIN_CREATE_OUTPUT" | grep "CREATED:" | cut -d' ' -f2)
            log_success "Администратор создан: $CREATED_USERNAME"
            log_info "  Email: $ADMIN_EMAIL"
            log_info "  Password: $ADMIN_PASSWORD"
            ADMIN_CREDENTIALS="Username: $CREATED_USERNAME\nEmail: $ADMIN_EMAIL\nPassword: $ADMIN_PASSWORD"
        else
            log_warn "Неожиданный результат создания администратора"
            ADMIN_CREDENTIALS="Используйте ./scripts/setup_admin.sh для создания администратора"
        fi
    else
        log_error "Ошибка создания администратора"
        echo "$ADMIN_CREATE_OUTPUT"
        log_warn "Вы можете создать администратора позже: ./scripts/setup_admin.sh"
        ADMIN_CREDENTIALS="Используйте ./scripts/setup_admin.sh для создания администратора"
    fi
else
    log_info "Создание администратора пропущено (CREATE_ADMIN=false)"
    ADMIN_CREDENTIALS="Используйте ./scripts/setup_admin.sh для создания администратора"
fi

# ============================================
# ШАГ 10: Установка Frontend зависимостей
# ============================================
log_step "Шаг 10: Установка Frontend зависимостей..."

if [ -d "frontend" ] && [ -f "frontend/package.json" ]; then
    if ! check_command npm; then
        log_error "npm не установлен. Frontend не будет установлен."
    else
        cd frontend
        log_info "Установка npm пакетов (это может занять несколько минут)..."
        if npm install --silent --no-audit --no-fund 2>&1 | tail -5; then
            log_success "Frontend зависимости установлены"
        else
            log_error "Ошибка установки frontend зависимостей"
            log_warn "Продолжаем установку без frontend..."
        fi
        cd ..
    fi
else
    log_warn "Директория frontend или package.json не найдены, пропускаем установку frontend"
fi

# ============================================
# ШАГ 11: Сборка Frontend
# ============================================
log_step "Шаг 11: Сборка Frontend..."

if [ -d "frontend" ] && [ -f "frontend/package.json" ] && [ -d "frontend/node_modules" ]; then
    cd frontend
    log_info "Сборка frontend проекта (это может занять несколько минут)..."
    BUILD_OUTPUT=$(npm run build 2>&1)
    BUILD_EXIT_CODE=$?
    
    if [ $BUILD_EXIT_CODE -eq 0 ]; then
        echo "$BUILD_OUTPUT" | grep -E "(built|dist)" | tail -3
        log_success "Frontend собран успешно"
    else
        echo "$BUILD_OUTPUT" | tail -20
        log_error "Ошибка сборки frontend"
        log_warn "Продолжаем установку. Frontend можно собрать позже: cd frontend && npm run build"
    fi
    cd ..
elif [ ! -d "frontend/node_modules" ] && [ -d "frontend" ]; then
    log_warn "Frontend зависимости не установлены, пропускаем сборку"
    log_info "Установите зависимости и соберите позже: cd frontend && npm install && npm run build"
else
    log_warn "Директория frontend не найдена, пропускаем сборку"
fi

# ============================================
# ШАГ 12: Настройка прав доступа
# ============================================
log_step "Шаг 12: Настройка прав доступа..."

if [ "$SYSTEM_USER" != "$(whoami)" ] && id "$SYSTEM_USER" &>/dev/null; then
    chown -R "$SYSTEM_USER:$SYSTEM_USER" "$PROJECT_DIR" 2>/dev/null || {
        log_warn "Не удалось изменить владельца на $SYSTEM_USER. Продолжаем..."
    }
fi
chmod +x scripts/*.sh 2>/dev/null || true
chmod 600 .env 2>/dev/null || true
chmod 755 "$PROJECT_DIR" 2>/dev/null || true
log_success "Права доступа настроены"

# ============================================
# ШАГ 13: Создание systemd service
# ============================================
log_step "Шаг 13: Настройка systemd service..."

if [ "$CREATE_SYSTEMD_SERVICE" = "true" ]; then
    SERVICE_FILE="/etc/systemd/system/mikrotik-2fa-vpn.service"
    
    # Создаем service файл с правильными путями
    log_info "Создание systemd service файла..."
    cat > "$SERVICE_FILE" << SERVICEEOF
[Unit]
Description=MikroTik 2FA VPN System
After=network.target
Wants=network-online.target

[Service]
Type=simple
User=$SYSTEM_USER
WorkingDirectory=$PROJECT_DIR
Environment="PATH=$PROJECT_DIR/venv/bin"
EnvironmentFile=$PROJECT_DIR/.env
ExecStart=$PROJECT_DIR/venv/bin/uvicorn backend.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=mikrotik-2fa-vpn

# Ограничения безопасности
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=$PROJECT_DIR/data $PROJECT_DIR/logs

[Install]
WantedBy=multi-user.target
SERVICEEOF
    
    systemctl daemon-reload
    
    log_success "Systemd service создан: $SERVICE_FILE"
    
    # Включаем автозагрузку
    if [ "$AUTO_START" = "true" ]; then
        systemctl enable mikrotik-2fa-vpn.service
        log_success "Автозагрузка включена"
    fi
else
    log_info "Создание systemd service пропущено (CREATE_SYSTEMD_SERVICE=false)"
fi

# ============================================
# ШАГ 14: Запуск сервиса
# ============================================
log_step "Шаг 14: Запуск сервиса..."

if [ "$CREATE_SYSTEMD_SERVICE" = "true" ] && systemctl list-unit-files | grep -q "mikrotik-2fa-vpn.service"; then
    # Останавливаем если уже запущен
    if systemctl is-active --quiet mikrotik-2fa-vpn.service 2>/dev/null; then
        log_info "Остановка существующего сервиса..."
        systemctl stop mikrotik-2fa-vpn.service || true
        sleep 2
    fi
    
    # Запускаем сервис
    log_info "Запуск сервиса..."
    if systemctl start mikrotik-2fa-vpn.service; then
        # Ждем и проверяем статус
        sleep 5
        if systemctl is-active --quiet mikrotik-2fa-vpn.service; then
            log_success "Сервис запущен и работает"
        else
            log_warn "Сервис запущен, но возможно еще инициализируется"
            log_info "Проверьте статус: systemctl status mikrotik-2fa-vpn.service"
        fi
    else
        log_error "Не удалось запустить сервис"
        log_info "Проверьте логи: journalctl -u mikrotik-2fa-vpn.service -n 50"
        systemctl status mikrotik-2fa-vpn.service --no-pager -l || true
        log_warn "Продолжаем установку. Запустите сервис вручную после проверки конфигурации."
    fi
else
    log_warn "Systemd service не настроен, автоматический запуск не выполнен"
    log_info "Для запуска используйте: ./scripts/start.sh"
fi

# ============================================
# ШАГ 15: Проверка работоспособности
# ============================================
log_step "Шаг 15: Проверка работоспособности..."

HEALTH_CHECK_ATTEMPTS=0
HEALTH_CHECK_MAX=6
HEALTH_CHECK_SUCCESS=false

while [ $HEALTH_CHECK_ATTEMPTS -lt $HEALTH_CHECK_MAX ]; do
    sleep 2
    if curl -sf http://localhost:8000/health > /dev/null 2>&1; then
        HEALTH_STATUS=$(curl -s http://localhost:8000/health 2>/dev/null || echo "недоступен")
        log_success "Backend отвечает на health check"
        log_info "Health status: $HEALTH_STATUS"
        HEALTH_CHECK_SUCCESS=true
        break
    else
        HEALTH_CHECK_ATTEMPTS=$((HEALTH_CHECK_ATTEMPTS + 1))
        if [ $HEALTH_CHECK_ATTEMPTS -lt $HEALTH_CHECK_MAX ]; then
            log_info "Ожидание запуска backend... ($HEALTH_CHECK_ATTEMPTS/$HEALTH_CHECK_MAX)"
        fi
    fi
done

if [ "$HEALTH_CHECK_SUCCESS" = false ]; then
    log_warn "Backend не отвечает на health check после $HEALTH_CHECK_MAX попыток"
    log_info "Сервис может еще запускаться. Проверьте: systemctl status mikrotik-2fa-vpn.service"
fi

# ============================================
# ФИНАЛЬНАЯ СВОДКА
# ============================================
echo ""
log_info "=========================================="
log_info "  Установка завершена успешно!"
log_info "=========================================="
echo ""
log_success "Проект установлен в: $PROJECT_DIR"
log_success "Системный пользователь: $SYSTEM_USER"

if [ "$CREATE_SYSTEMD_SERVICE" = "true" ]; then
    SERVICE_STATUS=$(systemctl is-active mikrotik-2fa-vpn.service 2>/dev/null || echo "unknown")
    log_success "Systemd service: mikrotik-2fa-vpn.service ($SERVICE_STATUS)"
    log_success "Автозагрузка: $([ "$AUTO_START" = "true" ] && echo "включена" || echo "выключена")"
fi

echo ""
log_info "🌐 Доступ к приложению:"
echo "   - Веб-интерфейс: http://localhost:8000"
echo "   - API документация: http://localhost:8000/docs"
echo "   - API альтернативная: http://localhost:8000/redoc"
echo ""

log_info "🔐 Учетные данные администратора:"
echo -e "   $ADMIN_CREDENTIALS" | sed 's/^/   /' | sed 's/\\n/\n   /g'
echo ""

log_warn "⚠️  ВАЖНО: Смените пароль администратора после первого входа!"
echo ""

log_info "📝 Полезные команды:"
echo "   - Статус сервиса: systemctl status mikrotik-2fa-vpn"
echo "   - Остановка: systemctl stop mikrotik-2fa-vpn"
echo "   - Запуск: systemctl start mikrotik-2fa-vpn"
echo "   - Перезапуск: systemctl restart mikrotik-2fa-vpn"
echo "   - Логи: journalctl -u mikrotik-2fa-vpn.service -f"
echo ""
log_info "🎯 Следующий шаг: Настройка через веб-интерфейс"
echo "   1. Откройте: http://localhost:8000"
echo "   2. Войдите с учетными данными выше"
echo "   3. Пройдите мастер настройки (все параметры настраиваются там!)"
echo ""

log_info "📚 Документация:"
echo "   - Быстрый старт: $PROJECT_DIR/QUICK_START.md"
echo "   - Общая информация: $PROJECT_DIR/README.md"
echo ""

# Сохраняем учетные данные в файл (для безопасности можно удалить позже)
if [ "$CREATE_ADMIN" = "true" ] && echo "$ADMIN_CREDENTIALS" | grep -q "Password:"; then
    CREDENTIALS_FILE="$PROJECT_DIR/.admin_credentials.txt"
    cat > "$CREDENTIALS_FILE" << CREDEOF
MikroTik 2FA VPN System - Учетные данные администратора
=======================================================
Дата создания: $(date)

$ADMIN_CREDENTIALS

⚠️ ВАЖНО: Сохраните эти данные в безопасном месте и удалите этот файл!
Удалить файл: rm $CREDENTIALS_FILE

CREDEOF
    chmod 600 "$CREDENTIALS_FILE"
    if [ "$SYSTEM_USER" != "$(whoami)" ] && id "$SYSTEM_USER" &>/dev/null; then
        chown "$SYSTEM_USER:$SYSTEM_USER" "$CREDENTIALS_FILE" 2>/dev/null || true
    fi
    log_warn "Учетные данные сохранены в: $CREDENTIALS_FILE"
    log_warn "Удалите этот файл после сохранения данных в безопасном месте!"
    echo ""
fi

log_success "Установка полностью завершена!"
echo ""
