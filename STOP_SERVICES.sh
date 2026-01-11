#!/usr/bin/env bash

# Совместимая остановка backend. Рекомендуемый способ — через systemd:
#   sudo systemctl stop mikrotik-2fa-vpn

set -euo pipefail

echo "Остановка MikroTik 2FA VPN System..."

if command -v systemctl >/dev/null 2>&1 && systemctl list-unit-files 2>/dev/null | grep -q '^mikrotik-2fa-vpn\.service'; then
  if [[ "${EUID}" -ne 0 ]]; then
    sudo systemctl stop mikrotik-2fa-vpn || true
  else
    systemctl stop mikrotik-2fa-vpn || true
  fi
  echo "OK: сервис остановлен (systemd)"
  exit 0
fi

if [[ -f /tmp/mikrotik-2fa-vpn.pid ]]; then
  PID="$(cat /tmp/mikrotik-2fa-vpn.pid || true)"
  if [[ -n "${PID}" ]] && kill -0 "${PID}" 2>/dev/null; then
    kill "${PID}" || true
    rm -f /tmp/mikrotik-2fa-vpn.pid || true
    echo "OK: backend остановлен (PID: ${PID})"
    exit 0
  fi
fi

PID="$(pgrep -f "uvicorn backend.main:app" 2>/dev/null | head -n1 || true)"
if [[ -n "${PID}" ]]; then
  kill "${PID}" || true
  echo "OK: backend остановлен (PID: ${PID})"
else
  echo "OK: backend не запущен"
fi
