# Руководство по установке

## Установка “с нуля” (рекомендуется)

Подходит для новой системы, где проекта ещё нет на диске.

```bash
wget -O install.sh "https://raw.githubusercontent.com/netcore-24/2FA-Mikrotik-VPN/main/install.sh"
sudo bash install.sh
```

По умолчанию проект будет установлен в `/opt/mikrotik-2fa-vpn`, создан сервис `mikrotik-2fa-vpn.service` и приложение будет запущено.

## Если проект уже склонирован

```bash
cd /path/to/mikrotik-2fa-vpn
sudo bash install.sh
```

## Параметры установки

`install.sh` поддерживает переменные окружения:

```bash
export INSTALL_DIR="/opt/mikrotik-2fa-vpn"
export GIT_BRANCH="main"
export REPO_URL="https://github.com/netcore-24/2FA-Mikrotik-VPN.git"
export SYSTEM_USER="mikrotik-2fa"

export CREATE_SYSTEMD_SERVICE="true"
export AUTO_START="true"
export CREATE_ADMIN="true"

export ADMIN_USERNAME="admin"
export ADMIN_EMAIL="admin@example.com"
export ADMIN_PASSWORD=""          # если пусто — будет сгенерирован

export NON_INTERACTIVE="true"
```

## После установки

- **Веб-интерфейс**: `http://<IP_сервера>:8000`
- **Health**: `http://localhost:8000/health`

## Управление сервисом

```bash
sudo systemctl status mikrotik-2fa-vpn
sudo systemctl restart mikrotik-2fa-vpn
sudo journalctl -u mikrotik-2fa-vpn.service -n 100 --no-pager
```

## Переустановка (если нужно)

```bash
sudo systemctl stop mikrotik-2fa-vpn || true
sudo rm -rf /opt/mikrotik-2fa-vpn
wget -O install.sh "https://raw.githubusercontent.com/netcore-24/2FA-Mikrotik-VPN/main/install.sh"
sudo bash install.sh
```

