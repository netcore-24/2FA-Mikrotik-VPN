#!/bin/bash

# Скрипт для создания первого администратора

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

log_info "Создание первого администратора..."

# Проверяем наличие виртуального окружения
if [ ! -d "venv" ]; then
    log_error "Виртуальное окружение не найдено. Запустите сначала install.sh"
    exit 1
fi

# Активируем виртуальное окружение
source venv/bin/activate

# Проверяем наличие .env файла
if [ ! -f ".env" ]; then
    log_error ".env файл не найден. Создайте его на основе .env.example"
    exit 1
fi

# Запрашиваем данные администратора
echo ""
echo "Введите данные администратора:"
echo ""

read -p "Имя пользователя (username): " ADMIN_USERNAME
read -p "Email: " ADMIN_EMAIL
read -sp "Пароль: " ADMIN_PASSWORD
echo ""
read -sp "Подтвердите пароль: " ADMIN_PASSWORD_CONFIRM
echo ""

if [ "$ADMIN_PASSWORD" != "$ADMIN_PASSWORD_CONFIRM" ]; then
    log_error "Пароли не совпадают!"
    exit 1
fi

if [ -z "$ADMIN_USERNAME" ] || [ -z "$ADMIN_EMAIL" ] || [ -z "$ADMIN_PASSWORD" ]; then
    log_error "Все поля обязательны для заполнения!"
    exit 1
fi

read -p "Полное имя (необязательно): " ADMIN_FULL_NAME

# Создаем Python скрипт для создания администратора
python3 << EOF
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.database import init_db, SessionLocal
from backend.services.auth_service import create_admin
from backend.models.admin import Admin

# Инициализируем БД
init_db()

# Создаем администратора
db = SessionLocal()
try:
    # Проверяем, не существует ли уже администратор с таким именем
    existing_admin = db.query(Admin).filter(Admin.username == "$ADMIN_USERNAME").first()
    if existing_admin:
        print("Администратор с таким именем пользователя уже существует!")
        sys.exit(1)
    
    admin = create_admin(
        db=db,
        username="$ADMIN_USERNAME",
        email="$ADMIN_EMAIL",
        password="$ADMIN_PASSWORD",
        full_name="$ADMIN_FULL_NAME" if "$ADMIN_FULL_NAME" else None,
        is_super_admin=True,
    )
    print(f"\n✓ Администратор успешно создан!")
    print(f"  Username: {admin.username}")
    print(f"  Email: {admin.email}")
    print(f"  ID: {admin.id}")
except Exception as e:
    print(f"Ошибка при создании администратора: {e}")
    sys.exit(1)
finally:
    db.close()
EOF

if [ $? -eq 0 ]; then
    log_info "Администратор успешно создан!"
else
    log_error "Не удалось создать администратора"
    exit 1
fi
