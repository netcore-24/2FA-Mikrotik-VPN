# Quick Start

## 🚀 Install and start (1 command)

```bash
wget -O install.sh "https://raw.githubusercontent.com/netcore-24/2FA-Mikrotik-VPN/main/install.sh"
sudo bash install.sh
```

The installer will deploy the system, start the web UI, and print a URL like `http://<IP>:8000`.

## 🧭 Next — configure in the web UI

- Open the URL printed in the terminal
- Log in as admin (credentials are printed in the terminal; they may also be saved to `.admin_credentials.txt`)
- Go through the setup wizard (Telegram / MikroTik / other settings)

## 🛠 Service management

```bash
sudo systemctl status mikrotik-2fa-vpn
sudo systemctl restart mikrotik-2fa-vpn
sudo journalctl -u mikrotik-2fa-vpn.service -f
```

## 🤖 Telegram bot (optional)

The token is configured via the setup wizard in the web UI.

