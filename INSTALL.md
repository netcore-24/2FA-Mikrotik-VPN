# Установка MikroTik 2FA VPN System

## Установка “с нуля” (wget → sudo bash)

Подходит для новой системы, где проекта ещё нет на диске.

```bash
wget -O install.sh "https://raw.githubusercontent.com/sh034/2FA-Mikrotik-VPN/main/install.sh"
sudo bash install.sh
```

По умолчанию проект будет установлен в `/opt/mikrotik-2fa-vpn`, создан и включен сервис `mikrotik-2fa-vpn.service`, приложение будет запущено.

## Автоматическая установка (из локальной директории или из git)

Полный установщик: `scripts/install.sh`.

### Вариант 1: из локальной директории

```bash
cd /path/to/mikrotik-2fa-vpn
sudo bash scripts/install.sh
```

### Вариант 2: из git (если проект не скачан)

```bash
sudo \
  GIT_REPO="https://github.com/sh034/2FA-Mikrotik-VPN.git" \
  GIT_BRANCH="main" \
  bash scripts/install.sh
```

### Параметры установки (env)

```bash
export INSTALL_DIR="/opt/mikrotik-2fa-vpn"
export GIT_REPO="https://github.com/sh034/2FA-Mikrotik-VPN.git"
export GIT_BRANCH="main"
export SYSTEM_USER="mikrotik-2fa"
export CREATE_SYSTEMD_SERVICE="true"
export AUTO_START="true"
export CREATE_ADMIN="true"
export ADMIN_USERNAME="admin"
export ADMIN_EMAIL="admin@example.com"
export ADMIN_PASSWORD="your_password"  # если не указан — будет создан автоматически
export NON_INTERACTIVE="true"
```

## После установки

- **Веб-интерфейс**: `http://<IP_СЕРВЕРА>:8000`
- **Health**: `http://<IP_СЕРВЕРА>:8000/health`
- **API docs**: `http://<IP_СЕРВЕРА>:8000/docs`

## Управление сервисом

```bash
sudo systemctl status mikrotik-2fa-vpn
sudo systemctl restart mikrotik-2fa-vpn
sudo journalctl -u mikrotik-2fa-vpn.service -n 200 --no-pager
```
