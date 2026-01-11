# Installation Guide

## Fresh install (recommended)

Suitable for a brand-new system where the project is not yet present on disk.

```bash
wget -O install.sh "https://raw.githubusercontent.com/netcore-24/2FA-Mikrotik-VPN/main/install.sh"
sudo bash install.sh
```

By default, the project will be installed to `/opt/mikrotik-2fa-vpn`, a `mikrotik-2fa-vpn.service` systemd unit will be created, and the application will be started.

## If the project is already cloned

```bash
cd /path/to/mikrotik-2fa-vpn
sudo bash install.sh
```

## Installation parameters

`install.sh` supports the following environment variables:

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
export ADMIN_PASSWORD=""          # if empty — will be generated

export NON_INTERACTIVE="true"
```

## After installation

- **Web UI**: `http://<SERVER_IP>:8000`
- **Health**: `http://localhost:8000/health`

## Service management

```bash
sudo systemctl status mikrotik-2fa-vpn
sudo systemctl restart mikrotik-2fa-vpn
sudo journalctl -u mikrotik-2fa-vpn.service -n 100 --no-pager
```

## Reinstall (if needed)

```bash
sudo systemctl stop mikrotik-2fa-vpn || true
sudo rm -rf /opt/mikrotik-2fa-vpn
wget -O install.sh "https://raw.githubusercontent.com/netcore-24/2FA-Mikrotik-VPN/main/install.sh"
sudo bash install.sh
```

