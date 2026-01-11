# Deployment Guide

Detailed guide for installing and deploying the system on Debian 12–13.

## Requirements

- OS: Debian 12 (Bookworm) or Debian 13 (Trixie)
- Python 3.11+ (included in Debian 12+)
- SQLite 3.x (bundled with Python)
- At least 512MB RAM (recommended 1GB+)
- At least 1GB free disk space

## Automated installation

The project includes an automated installer script `install.sh` that performs the required setup.

### Installation steps

1. Clone or unpack the project:

```bash
cd /opt
git clone <repository-url> mikrotik-2fa-vpn
# or
tar -xzf mikrotik-2fa-vpn.tar.gz
cd mikrotik-2fa-vpn
```

2. Run the installer:

```bash
chmod +x install.sh
sudo ./install.sh
```

The script will:
- Check OS version
- Install system packages
- Create a Python virtual environment
- Install Python dependencies from `requirements.txt`
- Install Node.js dependencies (if needed)
- Create required directories
- Set permissions
- Create a systemd service (optional)

3. Configure environment variables:

```bash
cp .env.example .env
nano .env
```

Fill in required variables:
- `TELEGRAM_BOT_TOKEN`
- `DATABASE_URL` (optional; SQLite is used by default)
- `SECRET_KEY`
- and other settings

4. Database initialization:
The SQLite database file is created automatically on first start.

5. Start the application:

```bash
# Manual start
./scripts/start.sh

# Or via systemd
sudo systemctl start mikrotik-2fa-vpn
sudo systemctl enable mikrotik-2fa-vpn
```

6. Initial configuration via Setup Wizard:
After the app starts, open the web UI in a browser. On the first login, the Setup Wizard will start automatically and guide you through:

- Basic info (name, language, time zone)
- Security (secret key, first admin)
- Telegram Bot (token, connection test)
- MikroTik Router (connection and setup instructions)
- Notifications (admin notifications)
- Additional settings (optional)

You can start the wizard at any time from Settings → Setup Wizard.

More details: `setup_wizard.md`

## Manual installation

If you need a manual setup:

### 1. Install system packages

```bash
sudo apt update
sudo apt install -y python3 python3-pip python3-venv git
```

### 2. Install Python dependencies

```bash
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Install/build frontend (if needed)

```bash
cd frontend
npm install
npm run build
cd ..
```

### 4. Configure environment variables

```bash
cp .env.example .env
# edit .env
```

### 5. Migrations

Migrations run automatically on first start.

## Project dependencies

All dependencies are included:

- `requirements.txt` — Python dependencies
- `package.json` — frontend dependencies (if applicable)
- `install.sh` — list of system packages for Debian

## Backups

To back up the SQLite database:

```bash
# Manual backup
./scripts/backup_db.sh

# Automated backups can be configured via cron
```

SQLite is just a file, so backups are simple file copies.

## Updates

To update the system:

```bash
git pull  # or update project files
./scripts/update.sh
```

## Database structure

By default, the SQLite database is stored at `data/mikrotik_2fa.db`.

All tables are created automatically on first start via SQLAlchemy migrations.

## Troubleshooting

### Permission issues

```bash
sudo chown -R $USER:$USER /opt/mikrotik-2fa-vpn
chmod +x scripts/*.sh
```

### Dependency issues

```bash
source venv/bin/activate
pip install --upgrade -r requirements.txt
```

### Database issues

Check permissions for the database file and the `data/` directory:

```bash
ls -la data/
```

