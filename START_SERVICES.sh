#!/usr/bin/env bash

# Совместимый запуск backend. Рекомендуемый способ — через systemd:
#   sudo systemctl restart mikrotik-2fa-vpn

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="${SCRIPT_DIR}"

cd "${PROJECT_DIR}"

echo "Запуск MikroTik 2FA VPN System..."

if command -v systemctl >/dev/null 2>&1 && systemctl list-unit-files 2>/dev/null | grep -q '^mikrotik-2fa-vpn\.service'; then
  if [[ "${EUID}" -ne 0 ]]; then
    sudo systemctl restart mikrotik-2fa-vpn
  else
    systemctl restart mikrotik-2fa-vpn
  fi
  echo "OK: сервис перезапущен (systemd)"
  exit 0
fi

if [[ ! -d "venv" ]]; then
  echo "ERROR: venv не найден. Запустите установку: sudo bash ./install.sh" >&2
  exit 1
fi

mkdir -p logs
if pgrep -f "uvicorn backend.main:app" >/dev/null 2>&1; then
  echo "OK: backend уже запущен"
  exit 0
fi

nohup "${PROJECT_DIR}/venv/bin/uvicorn" backend.main:app --host 0.0.0.0 --port 8000 > "${PROJECT_DIR}/logs/backend.log" 2>&1 &
echo $! > /tmp/mikrotik-2fa-vpn.pid
echo "OK: backend запущен (PID: $(cat /tmp/mikrotik-2fa-vpn.pid))"
