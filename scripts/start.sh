#!/usr/bin/env bash

# Совместимый запуск backend. Рекомендуемый способ — через systemd:
#   sudo systemctl restart mikrotik-2fa-vpn

set -euo pipefail

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${PROJECT_ROOT}"
log_info "Запуск MikroTik 2FA VPN System..."

if command -v systemctl >/dev/null 2>&1 && systemctl list-unit-files 2>/dev/null | grep -q '^mikrotik-2fa-vpn\.service'; then
  if [[ "${EUID}" -ne 0 ]]; then
    sudo systemctl restart mikrotik-2fa-vpn
  else
    systemctl restart mikrotik-2fa-vpn
  fi
  log_info "Готово: сервис перезапущен (systemd)"
  exit 0
fi

if [[ ! -d "venv" ]]; then
  log_error "venv не найден. Запустите установку: sudo bash ./install.sh"
  exit 1
fi

mkdir -p data logs data/backups backups

exec "${PROJECT_ROOT}/venv/bin/uvicorn" backend.main:app --host 0.0.0.0 --port 8000
