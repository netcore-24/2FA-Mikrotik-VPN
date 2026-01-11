# System Requirements

## System requirements

### Server
- OS: Debian 12 (Bookworm) or Debian 13 (Trixie)
- Python: 3.11+ (included in Debian 12+)
- SQLite: 3.x (bundled with Python, no separate install required)
- RAM: minimum 512MB (recommended 1GB+)
- Disk: minimum 1GB free space (recommended 2GB+)
- Network: internet access and connectivity to the MikroTik router

### Minimum requirements for development
- OS: Debian 12+ or compatible
- Python 3.11+
- SQLite 3.x (typically included with Python)
- Node.js 18+ (frontend build, if needed)
- Git (to clone the repository)

## Dependencies

See `requirements.txt` and `package.json`.

## Access

### The system requires:
- Telegram Bot Token
- SSH access to the MikroTik router
  - SSH key or username/password
  - Admin privileges on the router

### Notes
- All dependencies are included in the project
- Python dependencies are listed in `requirements.txt`
- Frontend dependencies are listed in `package.json`
- Automated installation is available via `install.sh`

