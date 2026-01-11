#!/usr/bin/env bash

#
# MikroTik 2FA VPN System — ЕДИНЫЙ установщик/запуск
#
# Требование: "скачал скрипт → запустил → получил ссылку и веб уже готов".
#
# Использование:
#   wget -O install.sh "https://raw.githubusercontent.com/netcore-24/2FA-Mikrotik-VPN/main/install.sh"
#   sudo bash install.sh
#
# Переменные (опционально):
#   REPO_URL, GIT_BRANCH, INSTALL_DIR, SYSTEM_USER
#   CREATE_SYSTEMD_SERVICE=true|false
#   AUTO_START=true|false
#   CREATE_ADMIN=true|false
#   ADMIN_USERNAME, ADMIN_EMAIL, ADMIN_PASSWORD (если пусто — будет сгенерирован)
#   NON_INTERACTIVE=true|false
#

set -euo pipefail

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
log_step() { echo -e "${BLUE}[STEP]${NC} $1"; }
log_success() { echo -e "${CYAN}[✓]${NC} $1"; }

need_root() {
  if [[ "${EUID}" -ne 0 ]]; then
    log_error "Запустите с правами root: sudo bash install.sh"
    exit 1
  fi
}

have_cmd() { command -v "$1" >/dev/null 2>&1; }

INSTALL_DIR="${INSTALL_DIR:-/opt/mikrotik-2fa-vpn}"
REPO_URL="${REPO_URL:-${GIT_REPO:-https://github.com/netcore-24/2FA-Mikrotik-VPN.git}}"
GIT_BRANCH="${GIT_BRANCH:-main}"
SYSTEM_USER="${SYSTEM_USER:-mikrotik-2fa}"

CREATE_SYSTEMD_SERVICE="${CREATE_SYSTEMD_SERVICE:-true}"
AUTO_START="${AUTO_START:-true}"
CREATE_ADMIN="${CREATE_ADMIN:-true}"
NON_INTERACTIVE="${NON_INTERACTIVE:-true}"

ADMIN_USERNAME="${ADMIN_USERNAME:-admin}"
ADMIN_EMAIL="${ADMIN_EMAIL:-admin@example.com}"
ADMIN_PASSWORD="${ADMIN_PASSWORD:-}"

PROJECT_DIR=""
ADMIN_CREDENTIALS="Используйте мастер настройки в веб-интерфейсе или ./scripts/setup_admin.sh"

detect_ip() {
  local ip=""
  if have_cmd ip; then
    ip="$(ip -4 route get 1.1.1.1 2>/dev/null | awk '{for(i=1;i<=NF;i++) if($i=="src") {print $(i+1); exit}}' || true)"
  fi
  if [[ -z "${ip}" ]] && have_cmd hostname; then
    ip="$(hostname -I 2>/dev/null | awk '{print $1}' || true)"
  fi
  if [[ -z "${ip}" ]]; then
    ip="localhost"
  fi
  echo "${ip}"
}

pm_update() {
  if have_cmd apt-get; then
    DEBIAN_FRONTEND=noninteractive apt-get update -qq
    return 0
  fi
  if have_cmd dnf; then
    dnf -y makecache >/dev/null
    return 0
  fi
  if have_cmd yum; then
    yum -y makecache >/dev/null
    return 0
  fi
  if have_cmd pacman; then
    pacman -Sy --noconfirm >/dev/null
    return 0
  fi
  log_error "Не удалось определить менеджер пакетов (apt-get/dnf/yum/pacman)."
  exit 1
}

pm_install() {
  local pkgs=("$@")
  if have_cmd apt-get; then
    DEBIAN_FRONTEND=noninteractive apt-get install -y "${pkgs[@]}"
    return 0
  fi
  if have_cmd dnf; then
    dnf install -y "${pkgs[@]}"
    return 0
  fi
  if have_cmd yum; then
    yum install -y "${pkgs[@]}"
    return 0
  fi
  if have_cmd pacman; then
    pacman -S --noconfirm "${pkgs[@]}"
    return 0
  fi
  log_error "Не удалось определить менеджер пакетов (apt-get/dnf/yum/pacman)."
  exit 1
}

ensure_base_packages() {
  log_step "Подготовка системы (git/curl/ca-certificates)..."
  if ! have_cmd git || ! have_cmd curl; then
    pm_update
    pm_install ca-certificates curl git
  fi
}

ensure_python() {
  log_step "Проверка Python..."
  if ! have_cmd python3; then
    pm_update
    pm_install python3
  fi
  local v
  v="$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))' 2>/dev/null || true)"
  if [[ -z "${v}" ]]; then
    log_error "Не удалось определить версию python3"
    exit 1
  fi
  # Требуем 3.11+ (как в README проекта)
  if [[ "$(printf '%s\n' "3.11" "${v}" | sort -V | head -n1)" != "3.11" ]]; then
    log_error "Требуется Python 3.11+. Установлен: ${v}"
    exit 1
  fi
  log_success "Python ${v} найден"

  log_step "Установка системных библиотек для Python зависимостей..."
  pm_update
  if have_cmd apt-get; then
    pm_install python3-venv python3-pip python3-dev build-essential libssl-dev libffi-dev
  elif have_cmd dnf || have_cmd yum; then
    pm_install python3-pip python3-devel gcc gcc-c++ openssl-devel libffi-devel
  else
    # pacman / прочие
    pm_install python-pip python-virtualenv
  fi
}

ensure_node() {
  # Нужен только если есть frontend/
  if [[ ! -d "${PROJECT_DIR}/frontend" || ! -f "${PROJECT_DIR}/frontend/package.json" ]]; then
    return 0
  fi

  log_step "Проверка Node.js (для сборки frontend)..."
  local need_install="false"
  if ! have_cmd node || ! have_cmd npm; then
    need_install="true"
  else
    local major
    major="$(node -p 'process.versions.node.split(".")[0]' 2>/dev/null || echo "0")"
    if [[ "${major}" -lt 18 ]]; then
      need_install="true"
    fi
  fi

  if [[ "${need_install}" == "true" ]]; then
    if ! have_cmd curl; then
      pm_update
      pm_install ca-certificates curl
    fi
    if have_cmd apt-get; then
      log_info "Устанавливаю Node.js 20.x (NodeSource)..."
      curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
      pm_update
      pm_install nodejs
    else
      pm_update
      pm_install nodejs npm || true
    fi
  fi

  if have_cmd node && have_cmd npm; then
    log_success "Node.js $(node --version) и npm $(npm --version) готовы"
  else
    log_warn "Node.js/npm не установлены — frontend будет пропущен (backend продолжит работать)."
  fi
}

use_local_or_clone() {
  # Если запущено из директории проекта — используем её.
  if [[ -f "./backend/main.py" && -f "./requirements.txt" ]]; then
    PROJECT_DIR="$(pwd)"
    log_info "Обнаружен локальный проект: ${PROJECT_DIR}"
    return 0
  fi

  ensure_base_packages

  log_step "Клонирование проекта в ${INSTALL_DIR}..."
  if [[ -d "${INSTALL_DIR}/.git" ]]; then
    log_info "Проект уже есть — обновляю (ветка: ${GIT_BRANCH})"
    git -C "${INSTALL_DIR}" fetch --all --prune
    git -C "${INSTALL_DIR}" checkout "${GIT_BRANCH}"
    git -C "${INSTALL_DIR}" pull --ff-only
  else
    if [[ -d "${INSTALL_DIR}" && -n "$(ls -A "${INSTALL_DIR}" 2>/dev/null || true)" ]]; then
      log_error "Директория ${INSTALL_DIR} существует и не пуста. Удалите её или укажите INSTALL_DIR другой."
      exit 1
    fi
    mkdir -p "${INSTALL_DIR}"
    git clone -b "${GIT_BRANCH}" "${REPO_URL}" "${INSTALL_DIR}"
  fi

  PROJECT_DIR="${INSTALL_DIR}"
}

ensure_system_user() {
  log_step "Создание системного пользователя (${SYSTEM_USER})..."
  if id "${SYSTEM_USER}" >/dev/null 2>&1; then
    log_info "Пользователь ${SYSTEM_USER} уже существует"
    return 0
  fi

  # Создаём системного пользователя под запуск сервиса.
  if useradd -r -s /bin/bash -d "${PROJECT_DIR}" -m "${SYSTEM_USER}" 2>/dev/null; then
    log_success "Пользователь ${SYSTEM_USER} создан"
  else
    log_warn "Не удалось создать пользователя ${SYSTEM_USER}. Продолжаю с текущим пользователем."
    SYSTEM_USER="$(whoami)"
  fi
}

ensure_env() {
  log_step "Настройка .env..."
  cd "${PROJECT_DIR}"

  if [[ -f ".env" ]]; then
    log_info ".env уже существует — не перезаписываю"
    return 0
  fi

  local secret_key encryption_key
  secret_key="$("${PROJECT_DIR}/venv/bin/python" -c "import secrets; print(secrets.token_hex(32))")"
  encryption_key="$("${PROJECT_DIR}/venv/bin/python" -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")"

  cat > .env <<EOF
# Основные настройки приложения
APP_NAME=MikroTik 2FA VPN System
APP_VERSION=1.0.0
DEBUG=False
LANGUAGE=ru

# База данных
DATABASE_URL=sqlite:///./data/mikrotik_2fa.db

# JWT токены
SECRET_KEY=${secret_key}
JWT_SECRET_KEY=${secret_key}
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=1440
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7

# CORS
CORS_ORIGINS=["http://localhost:3000","http://localhost:5173","http://localhost:8000"]

# Telegram Bot (можно настроить позже через мастер)
TELEGRAM_BOT_TOKEN=

# MikroTik (можно настроить позже через мастер)
MIKROTIK_HOST=
MIKROTIK_PORT=22
MIKROTIK_USERNAME=
MIKROTIK_PASSWORD=
MIKROTIK_USE_SSL=False

# Бэкапы
BACKUP_PATH=./data/backups

# Шифрование
ENCRYPTION_KEY=${encryption_key}
EOF

  chmod 600 .env || true
  log_success ".env создан"
}

ensure_dirs() {
  log_step "Создание директорий данных..."
  cd "${PROJECT_DIR}"
  mkdir -p data logs data/backups backups || true
  log_success "Директории готовы"
}

ensure_venv_and_deps() {
  log_step "Создание виртуального окружения и установка зависимостей..."
  cd "${PROJECT_DIR}"

  if [[ ! -d "venv" ]]; then
    python3 -m venv venv
    log_success "venv создан"
  else
    log_info "venv уже существует"
  fi

  ./venv/bin/pip install --upgrade pip setuptools wheel
  ./venv/bin/pip install -r requirements.txt
  log_success "Python зависимости установлены"
}

init_database() {
  log_step "Инициализация базы данных..."
  cd "${PROJECT_DIR}"
  ./venv/bin/python -c "from backend.database import init_db; init_db()"
  log_success "База данных инициализирована"
}

create_admin_user() {
  if [[ "${CREATE_ADMIN}" != "true" ]]; then
    return 0
  fi

  log_step "Создание администратора..."
  cd "${PROJECT_DIR}"

  if [[ -z "${ADMIN_PASSWORD}" ]]; then
    ADMIN_PASSWORD="$(./venv/bin/python -c 'import secrets; print(secrets.token_urlsafe(9)[:12])')"
  fi

  export ADMIN_USERNAME ADMIN_EMAIL ADMIN_PASSWORD

  local out
  out="$(./venv/bin/python <<'PY'
import sys, os
sys.path.insert(0, os.getcwd())

from backend.database import SessionLocal
from backend.services.auth_service import create_admin, get_admin_by_username

db = SessionLocal()
try:
    u = os.environ.get("ADMIN_USERNAME", "admin")
    e = os.environ.get("ADMIN_EMAIL", "admin@example.com")
    p = os.environ.get("ADMIN_PASSWORD", "")

    existing = get_admin_by_username(db, u)
    if existing:
        print(f"EXISTS:{existing.username}")
    else:
        admin = create_admin(db=db, username=u, email=e, password=p, full_name="System Administrator", is_super_admin=True)
        print(f"CREATED:{admin.username}")
        print(f"EMAIL:{admin.email}")
        print(f"PASSWORD:{p}")
finally:
    db.close()
PY
)"

  if echo "${out}" | grep -q '^EXISTS:'; then
    ADMIN_CREDENTIALS="Администратор уже существует: ${ADMIN_USERNAME}"
    log_info "${ADMIN_CREDENTIALS}"
  elif echo "${out}" | grep -q '^CREATED:'; then
    ADMIN_CREDENTIALS="Username: ${ADMIN_USERNAME}\nEmail: ${ADMIN_EMAIL}\nPassword: ${ADMIN_PASSWORD}"
    log_success "Администратор создан: ${ADMIN_USERNAME}"
  else
    log_warn "Не удалось определить результат создания администратора"
  fi

  # Сохраняем в файл (удалить после сохранения!)
  local cred_file="${PROJECT_DIR}/.admin_credentials.txt"
  if echo "${ADMIN_CREDENTIALS}" | grep -q "Password:"; then
    cat > "${cred_file}" <<EOF
MikroTik 2FA VPN System - Учетные данные администратора
=======================================================
Дата: $(date)

${ADMIN_CREDENTIALS}

⚠️ ВАЖНО: удалите этот файл после сохранения данных.
rm -f "${cred_file}"
EOF
    chmod 600 "${cred_file}" || true
    chown "${SYSTEM_USER}:${SYSTEM_USER}" "${cred_file}" 2>/dev/null || true
    log_warn "Учетные данные сохранены в: ${cred_file}"
  fi
}

build_frontend() {
  if [[ ! -d "${PROJECT_DIR}/frontend" || ! -f "${PROJECT_DIR}/frontend/package.json" ]]; then
    return 0
  fi
  if ! have_cmd npm; then
    log_warn "npm не найден — пропускаю сборку frontend"
    return 0
  fi

  log_step "Установка и сборка Frontend..."
  cd "${PROJECT_DIR}/frontend"
  if [[ -f "package-lock.json" ]]; then
    npm ci --no-audit --no-fund
  else
    npm install --no-audit --no-fund
  fi
  npm run build
  log_success "Frontend собран"
}

can_use_systemd() {
  have_cmd systemctl || return 1
  systemctl list-units >/dev/null 2>&1 || return 1
  return 0
}

setup_systemd_service() {
  if [[ "${CREATE_SYSTEMD_SERVICE}" != "true" ]]; then
    return 0
  fi
  if ! can_use_systemd; then
    log_warn "systemd недоступен — сервис не будет создан (запуск будет в фоне)."
    return 0
  fi

  log_step "Настройка systemd сервиса..."
  local service_file="/etc/systemd/system/mikrotik-2fa-vpn.service"
  cat > "${service_file}" <<EOF
[Unit]
Description=MikroTik 2FA VPN System
After=network.target
Wants=network-online.target

[Service]
Type=simple
User=${SYSTEM_USER}
WorkingDirectory=${PROJECT_DIR}
Environment="PATH=${PROJECT_DIR}/venv/bin"
Environment="PYTHONUNBUFFERED=1"
EnvironmentFile=${PROJECT_DIR}/.env
ExecStart=${PROJECT_DIR}/venv/bin/uvicorn backend.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=mikrotik-2fa-vpn

NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=${PROJECT_DIR}/data ${PROJECT_DIR}/logs ${PROJECT_DIR}/.env ${PROJECT_DIR}/backups ${PROJECT_DIR}/data/backups

[Install]
WantedBy=multi-user.target
EOF

  systemctl daemon-reload
  log_success "Сервис создан: mikrotik-2fa-vpn.service"

  if [[ "${AUTO_START}" == "true" ]]; then
    systemctl enable mikrotik-2fa-vpn.service
    log_success "Автозагрузка включена"
  fi
}

start_app() {
  log_step "Запуск приложения..."
  cd "${PROJECT_DIR}"

  if can_use_systemd && [[ "${CREATE_SYSTEMD_SERVICE}" == "true" ]]; then
    systemctl restart mikrotik-2fa-vpn.service
    log_success "Сервис перезапущен"
    return 0
  fi

  # Fallback: запуск в фоне (если systemd нет)
  mkdir -p logs
  if pgrep -f "uvicorn backend.main:app" >/dev/null 2>&1; then
    log_info "Backend уже запущен (uvicorn backend.main:app)"
    return 0
  fi
  nohup "${PROJECT_DIR}/venv/bin/uvicorn" backend.main:app --host 0.0.0.0 --port 8000 > "${PROJECT_DIR}/logs/backend.log" 2>&1 &
  echo $! > /tmp/mikrotik-2fa-vpn.pid
  log_success "Backend запущен в фоне (PID: $(cat /tmp/mikrotik-2fa-vpn.pid))"
}

wait_health() {
  log_step "Ожидание готовности (health-check)..."
  local max=30
  local i=0
  while [[ "${i}" -lt "${max}" ]]; do
    if curl -fsS "http://127.0.0.1:8000/health" >/dev/null 2>&1; then
      log_success "Backend отвечает на /health"
      return 0
    fi
    i=$((i+1))
    sleep 2
  done
  log_warn "Backend не ответил на /health за ~60 секунд. Проверьте логи."
  if can_use_systemd; then
    log_info "Логи: journalctl -u mikrotik-2fa-vpn.service -n 100 --no-pager"
  else
    log_info "Логи: tail -n 200 ${PROJECT_DIR}/logs/backend.log"
  fi
  return 0
}

fix_permissions() {
  log_step "Настройка прав доступа..."
  chown -R "${SYSTEM_USER}:${SYSTEM_USER}" "${PROJECT_DIR}" 2>/dev/null || true
  chmod -R u+rwX,go-rwx "${PROJECT_DIR}/.env" 2>/dev/null || true
  chmod +x "${PROJECT_DIR}/scripts/"*.sh 2>/dev/null || true
  log_success "Права настроены"
}

final_summary() {
  local ip port
  ip="$(detect_ip)"
  port="8000"
  local cred_file
  cred_file="${PROJECT_DIR}/.admin_credentials.txt"
  echo ""
  log_info "=========================================="
  log_info "  Установка завершена"
  log_info "=========================================="
  echo ""
  log_success "Проект: ${PROJECT_DIR}"
  log_success "Пользователь: ${SYSTEM_USER}"
  echo ""
  log_info "🌐 Доступ к сервису:"
  echo "   - IP:   ${ip}"
  echo "   - Port: ${port}"
  echo "   - Web:  http://${ip}:${port}"
  echo "   - Docs: http://${ip}:${port}/docs"
  echo ""
  log_info "🔐 Учетные данные администратора:"
  echo -e "   ${ADMIN_CREDENTIALS}" | sed 's/^/   /' | sed 's/\\n/\n   /g'
  if [[ -f "${cred_file}" ]]; then
    echo ""
    log_info "📄 Файл с учетными данными (если был сгенерирован пароль):"
    echo "   - Path: ${cred_file}"
    echo "   - Show: sudo cat ${cred_file}"
    echo "   - Remove after saving: sudo rm -f ${cred_file}"
  fi
  echo ""
  log_info "Управление:"
  if can_use_systemd; then
    echo "   - Статус:   systemctl status mikrotik-2fa-vpn"
    echo "   - Рестарт:  systemctl restart mikrotik-2fa-vpn"
    echo "   - Логи:     journalctl -u mikrotik-2fa-vpn.service -f"
  else
    echo "   - Остановка: kill \$(cat /tmp/mikrotik-2fa-vpn.pid)"
  fi
  echo ""
}

main() {
  need_root

  use_local_or_clone
  ensure_python
  ensure_dirs
  ensure_venv_and_deps
  ensure_env
  ensure_system_user
  fix_permissions
  ensure_node
  build_frontend
  init_database
  create_admin_user
  setup_systemd_service
  start_app
  wait_health
  final_summary
}

main "$@"
