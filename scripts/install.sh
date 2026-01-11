#!/usr/bin/env bash

# DEPRECATED: единый установщик теперь в корне репозитория: ./install.sh
# Оставлено как совместимость со старыми инструкциями.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

echo "[INFO] scripts/install.sh устарел. Используйте: sudo bash ${PROJECT_ROOT}/install.sh"
exec env \
  REPO_URL="${REPO_URL:-}" \
  GIT_REPO="${GIT_REPO:-}" \
  GIT_BRANCH="${GIT_BRANCH:-}" \
  INSTALL_DIR="${INSTALL_DIR:-}" \
  SYSTEM_USER="${SYSTEM_USER:-}" \
  CREATE_SYSTEMD_SERVICE="${CREATE_SYSTEMD_SERVICE:-}" \
  AUTO_START="${AUTO_START:-}" \
  CREATE_ADMIN="${CREATE_ADMIN:-}" \
  ADMIN_USERNAME="${ADMIN_USERNAME:-}" \
  ADMIN_EMAIL="${ADMIN_EMAIL:-}" \
  ADMIN_PASSWORD="${ADMIN_PASSWORD:-}" \
  NON_INTERACTIVE="${NON_INTERACTIVE:-}" \
  bash "${PROJECT_ROOT}/install.sh"
