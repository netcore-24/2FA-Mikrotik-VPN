# Руководство по установке MikroTik 2FA VPN System

## Автоматическая установка

Проект включает полностью автоматизированный скрипт установки, который:
- Скачивает проект из git репозитория
- Проверяет и устанавливает системные зависимости
- Создает виртуальное окружение Python
- Устанавливает все необходимые зависимости
- Инициализирует базу данных
- Создает systemd service
- Настраивает права доступа

### Быстрая установка

```bash
# Клонируйте репозиторий и запустите скрипт установки
sudo bash -c "$(curl -fsSL https://raw.githubusercontent.com/ВАШ_РЕПОЗИТОРИЙ/main/scripts/install.sh)"
```

Или вручную:

```bash
# Скачайте скрипт установки
curl -O https://raw.githubusercontent.com/ВАШ_РЕПОЗИТОРИЙ/main/scripts/install.sh

# Запустите установку
sudo bash install.sh
```

### Параметры установки

Скрипт поддерживает следующие переменные окружения:

```bash
# URL git репозитория (обязательно)
export GIT_REPO="https://github.com/ваш-username/mikrotik-2fa-vpn.git"

# Ветка для клонирования (по умолчанию: main)
export GIT_BRANCH="main"

# Директория установки (по умолчанию: /opt/mikrotik-2fa-vpn)
export INSTALL_DIR="/opt/mikrotik-2fa-vpn"

# Системный пользователь (по умолчанию: mikrotik-2fa)
export SYSTEM_USER="mikrotik-2fa"

# Создать systemd service (по умолчанию: true)
export CREATE_SYSTEMD_SERVICE="true"

# Создать симлинк (по умолчанию: false)
export CREATE_SYMLINK="false"
```

### Пример установки с параметрами

```bash
sudo GIT_REPO="https://github.com/ваш-username/mikrotik-2fa-vpn.git" \
     GIT_BRANCH="main" \
     INSTALL_DIR="/opt/mikrotik-2fa-vpn" \
     bash install.sh
```

## Ручная установка

Если вы предпочитаете установку вручную, выполните следующие шаги:

### 1. Системные требования

- Python 3.8 или выше
- Git
- pip3
- Linux система (рекомендуется Ubuntu/Debian или CentOS/RHEL)

### 2. Установка зависимостей

**Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install -y python3 python3-pip python3-venv git
```

**CentOS/RHEL:**
```bash
sudo yum install -y python3 python3-pip git
```

### 3. Клонирование репозитория

```bash
git clone https://github.com/ваш-username/mikrotik-2fa-vpn.git
cd mikrotik-2fa-vpn
```

### 4. Создание виртуального окружения

```bash
python3 -m venv venv
source venv/bin/activate
```

### 5. Установка Python зависимостей

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 6. Настройка конфигурации

```bash
cp .env.example .env
nano .env  # Отредактируйте необходимые параметры
```

### 7. Инициализация базы данных

```bash
python3 -c "from backend.database import init_db; init_db()"
```

### 8. Создание администратора

```bash
./scripts/setup_admin.sh
```

### 9. Запуск приложения

**Через systemd (рекомендуется):**
```bash
sudo cp mikrotik-2fa-vpn.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable mikrotik-2fa-vpn
sudo systemctl start mikrotik-2fa-vpn
```

**Вручную:**
```bash
./scripts/start.sh
```

### 10. Запуск Telegram бота

```bash
./scripts/start_bot.sh
```

Или через systemd (если создан отдельный service файл для бота).

## После установки

1. **Настройте конфигурацию** - отредактируйте `.env` файл:
   - `TELEGRAM_BOT_TOKEN` - токен вашего Telegram бота
   - `MIKROTIK_HOST` - адрес вашего MikroTik роутера
   - `SECRET_KEY` и `JWT_SECRET_KEY` - должны быть сгенерированы автоматически

2. **Создайте первого администратора:**
   ```bash
   ./scripts/setup_admin.sh
   ```

3. **Запустите приложение:**
   ```bash
   sudo systemctl start mikrotik-2fa-vpn
   sudo systemctl status mikrotik-2fa-vpn
   ```

4. **Запустите Telegram бота:**
   ```bash
   ./scripts/start_bot.sh
   ```

5. **Проверьте доступность API:**
   - API документация: http://localhost:8000/docs
   - Health check: http://localhost:8000/health

## Обновление

Для обновления существующей установки:

```bash
cd /opt/mikrotik-2fa-vpn
sudo -u mikrotik-2fa ./scripts/backup_db.sh  # Создайте резервную копию
git pull origin main
source venv/bin/activate
pip install --upgrade -r requirements.txt
sudo systemctl restart mikrotik-2fa-vpn
```

Или используйте скрипт обновления:

```bash
./scripts/update.sh
```

## Удаление

```bash
sudo systemctl stop mikrotik-2fa-vpn
sudo systemctl disable mikrotik-2fa-vpn
sudo rm /etc/systemd/system/mikrotik-2fa-vpn.service
sudo systemctl daemon-reload
sudo rm -rf /opt/mikrotik-2fa-vpn
sudo userdel mikrotik-2fa
```

## Поддержка

При возникновении проблем:
1. Проверьте логи: `journalctl -u mikrotik-2fa-vpn -f`
2. Проверьте конфигурацию: `.env` файл
3. Убедитесь, что все зависимости установлены: `pip list`
4. Проверьте права доступа к директориям и файлам
