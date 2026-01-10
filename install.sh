#!/usr/bin/env bash

# Bootstrap installer for MikroTik 2FA VPN System
#
# Цель: чтобы на новой системе было достаточно:
#  1) wget -O install.sh https://raw.githubusercontent.com/<repo>/main/install.sh
#  2) sudo bash install.sh
#
# Скрипт сам:
# - установит git (если нет)
# - склонирует проект в /opt
# - запустит полный установщик scripts/install.sh

set -euo pipefail

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
log_step() { echo -e "${BLUE}[STEP]${NC} $1"; }

need_root() {
  if [[ "${EUID}" -ne 0 ]]; then
    log_error "Запустите с правами root: sudo bash install.sh"
    exit 1
  fi
}

have_cmd() { command -v "$1" >/dev/null 2>&1; }

install_packages() {
  # Минимум для клонирования и скачивания зависимостей
  if have_cmd apt-get; then
    DEBIAN_FRONTEND=noninteractive apt-get update -qq
    DEBIAN_FRONTEND=noninteractive apt-get install -y ca-certificates curl git >/dev/null
    return 0
  fi
  if have_cmd dnf; then
    dnf install -y ca-certificates curl git >/dev/null
    return 0
  fi
  if have_cmd yum; then
    yum install -y ca-certificates curl git >/dev/null
    return 0
  fi
  if have_cmd pacman; then
    pacman -Sy --noconfirm ca-certificates curl git >/dev/null
    return 0
  fi

  log_error "Не удалось определить менеджер пакетов (apt-get/dnf/yum/pacman)."
  exit 1
}

main() {
  need_root

  # Если скрипт запущен ИЗ репозитория (после git clone), просто запускаем основной установщик.
  if [[ -f "./scripts/install.sh" && -f "./backend/main.py" ]]; then
    log_info "Обнаружен локальный проект — запускаю scripts/install.sh"
    exec bash ./scripts/install.sh
  fi

  log_step "Подготовка системы (git/curl)..."
  if ! have_cmd git || ! have_cmd curl; then
    log_info "Устанавливаю системные пакеты (git/curl)..."
    install_packages
  fi
  if ! have_cmd git; then
    log_error "git не установлен и не удалось установить автоматически."
    exit 1
  fi

  # Настраиваем параметры (можно переопределить переменными окружения)
  local REPO_URL="${REPO_URL:-https://github.com/sh034/2FA-Mikrotik-VPN.git}"
  local GIT_BRANCH="${GIT_BRANCH:-main}"
  local INSTALL_DIR="${INSTALL_DIR:-/opt/mikrotik-2fa-vpn}"

  log_step "Клонирование проекта в ${INSTALL_DIR}..."
  if [[ -d "${INSTALL_DIR}/.git" ]]; then
    log_info "Проект уже склонирован — обновляю из git (ветка: ${GIT_BRANCH})"
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

  log_step "Запуск полного установщика (scripts/install.sh)..."
  cd "${INSTALL_DIR}"
  # Важно: основной скрипт сам установит Python/Node, соберёт фронт, создаст .env,
  # установит systemd сервис, включит автозагрузку и запустит приложение.
  exec env \
    NON_INTERACTIVE="${NON_INTERACTIVE:-true}" \
    INSTALL_DIR="${INSTALL_DIR}" \
    SYSTEM_USER="${SYSTEM_USER:-mikrotik-2fa}" \
    CREATE_SYSTEMD_SERVICE="${CREATE_SYSTEMD_SERVICE:-true}" \
    AUTO_START="${AUTO_START:-true}" \
    CREATE_ADMIN="${CREATE_ADMIN:-true}" \
    ADMIN_USERNAME="${ADMIN_USERNAME:-admin}" \
    ADMIN_EMAIL="${ADMIN_EMAIL:-admin@example.com}" \
    ADMIN_PASSWORD="${ADMIN_PASSWORD:-}" \
    bash ./scripts/install.sh
}

main "$@"
