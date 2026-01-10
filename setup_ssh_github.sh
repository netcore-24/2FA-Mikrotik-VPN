#!/bin/bash

# Скрипт для настройки SSH ключей для GitHub

set -e

echo "=========================================="
echo "Настройка SSH ключей для GitHub"
echo "=========================================="
echo ""

# Проверка наличия ssh-keygen
if ! command -v ssh-keygen &> /dev/null; then
    echo "❌ ssh-keygen не найден. Устанавливаю OpenSSH..."
    sudo apt update
    sudo apt install openssh-client -y
    echo "✅ OpenSSH установлен"
fi

# Создание директории .ssh если не существует
if [ ! -d "$HOME/.ssh" ]; then
    mkdir -p "$HOME/.ssh"
    chmod 700 "$HOME/.ssh"
    echo "✅ Директория ~/.ssh создана"
fi

# Определение пути к ключу
SSH_KEY_PATH="$HOME/.ssh/id_ed25519"
SSH_PUB_KEY_PATH="$HOME/.ssh/id_ed25519.pub"

# Проверка существования ключа
if [ -f "$SSH_KEY_PATH" ]; then
    echo "⚠️  SSH ключ уже существует: $SSH_KEY_PATH"
    read -p "Создать новый ключ? (y/n) [n]: " CREATE_NEW
    CREATE_NEW=${CREATE_NEW:-n}
    
    if [ "$CREATE_NEW" = "y" ]; then
        read -p "Введите email для нового ключа: " SSH_EMAIL
        SSH_EMAIL=${SSH_EMAIL:-$(git config user.email 2>/dev/null || echo "")}
        
        if [ -z "$SSH_EMAIL" ]; then
            read -p "Email не найден. Введите email: " SSH_EMAIL
        fi
        
        # Резервная копия старого ключа
        BACKUP_PATH="${SSH_KEY_PATH}.backup.$(date +%Y%m%d_%H%M%S)"
        mv "$SSH_KEY_PATH" "$BACKUP_PATH"
        [ -f "$SSH_PUB_KEY_PATH" ] && mv "$SSH_PUB_KEY_PATH" "${SSH_PUB_KEY_PATH}.backup.$(date +%Y%m%d_%H%M%S)"
        echo "✅ Старый ключ сохранен: $BACKUP_PATH"
        
        # Создание нового ключа
        ssh-keygen -t ed25519 -C "$SSH_EMAIL" -f "$SSH_KEY_PATH" -N ""
        echo "✅ Новый SSH ключ создан"
    else
        echo "✅ Используется существующий ключ"
    fi
else
    # Получение email
    SSH_EMAIL=$(git config user.email 2>/dev/null || echo "")
    
    if [ -z "$SSH_EMAIL" ]; then
        echo "Введите ваш email для SSH ключа (или нажмите Enter для пропуска):"
        read -p "Email: " SSH_EMAIL
        SSH_EMAIL=${SSH_EMAIL:-"github-key-$(hostname)"}
    fi
    
    echo ""
    echo "Создаю SSH ключ..."
    echo "Email: $SSH_EMAIL"
    echo ""
    
    # Создание ключа без парольной фразы (для автоматизации)
    # Если хотите защитить ключ паролем, удалите флаг -N "" и введите пароль
    ssh-keygen -t ed25519 -C "$SSH_EMAIL" -f "$SSH_KEY_PATH" -N ""
    
    echo ""
    echo "✅ SSH ключ создан успешно!"
fi

# Проверка существования публичного ключа
if [ ! -f "$SSH_PUB_KEY_PATH" ]; then
    echo "❌ Публичный ключ не найден: $SSH_PUB_KEY_PATH"
    exit 1
fi

echo ""
echo "=========================================="
echo "Ваш публичный SSH ключ:"
echo "=========================================="
echo ""

# Отображение публичного ключа
cat "$SSH_PUB_KEY_PATH"

echo ""
echo ""
echo "=========================================="
echo "Инструкция:"
echo "=========================================="
echo ""
echo "1. СКОПИРУЙТЕ ключ выше (начинается с 'ssh-ed25519' и заканчивается вашим email)"
echo ""
echo "2. Добавьте ключ на GitHub:"
echo "   - Откройте: https://github.com/settings/keys"
echo "   - Нажмите 'New SSH key'"
echo "   - Title: например 'My Server' или '$(hostname)'"
echo "   - Key: вставьте скопированный ключ"
echo "   - Нажмите 'Add SSH key'"
echo ""
read -p "Нажмите Enter после того, как добавите ключ на GitHub..."

echo ""
echo "=========================================="
echo "Проверка подключения к GitHub"
echo "=========================================="
echo ""

# Запуск ssh-agent и добавление ключа
if [ -z "$SSH_AUTH_SOCK" ]; then
    eval "$(ssh-agent -s)" > /dev/null
fi

# Добавление ключа в ssh-agent
ssh-add "$SSH_KEY_PATH" 2>/dev/null || echo "⚠️  Не удалось добавить ключ в ssh-agent (может быть уже добавлен)"

# Проверка подключения
echo "Проверяю подключение к GitHub..."
if ssh -T git@github.com 2>&1 | grep -q "successfully authenticated"; then
    echo "✅ Подключение к GitHub успешно!"
else
    SSH_OUTPUT=$(ssh -T git@github.com 2>&1 || true)
    if echo "$SSH_OUTPUT" | grep -q "Permission denied"; then
        echo "❌ Доступ запрещен. Убедитесь, что вы добавили ключ на GitHub."
        echo ""
        echo "Попробуйте снова:"
        echo "1. Проверьте, что ключ добавлен: https://github.com/settings/keys"
        echo "2. Проверьте, что скопировали весь ключ (включая ssh-ed25519 и email)"
        echo ""
        read -p "Нажмите Enter для повторной проверки..."
        ssh -T git@github.com
    else
        echo "$SSH_OUTPUT"
    fi
fi

echo ""
echo "=========================================="
echo "Настройка Git для использования SSH"
echo "=========================================="
echo ""

# Переход в директорию проекта
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Проверка существующего remote
if git remote | grep -q "^origin$"; then
    EXISTING_URL=$(git remote get-url origin)
    echo "Найден существующий remote 'origin': $EXISTING_URL"
    
    # Проверка, используется ли уже SSH
    if echo "$EXISTING_URL" | grep -q "^git@github.com:"; then
        echo "✅ Remote уже использует SSH: $EXISTING_URL"
        
        read -p "Изменить username в remote? (y/n) [n]: " CHANGE_USERNAME
        CHANGE_USERNAME=${CHANGE_USERNAME:-n}
        
        if [ "$CHANGE_USERNAME" = "y" ]; then
            read -p "Введите ваш GitHub username: " GITHUB_USERNAME
            git remote set-url origin "git@github.com:${GITHUB_USERNAME}/mikrotik-2fa-vpn.git"
            echo "✅ Remote обновлен: git@github.com:${GITHUB_USERNAME}/mikrotik-2fa-vpn.git"
        fi
    else
        # Преобразование HTTPS в SSH
        echo "Преобразую HTTPS remote в SSH..."
        read -p "Введите ваш GitHub username: " GITHUB_USERNAME
        git remote set-url origin "git@github.com:${GITHUB_USERNAME}/mikrotik-2fa-vpn.git"
        echo "✅ Remote обновлен на SSH: git@github.com:${GITHUB_USERNAME}/mikrotik-2fa-vpn.git"
    fi
else
    # Создание нового remote
    read -p "Введите ваш GitHub username: " GITHUB_USERNAME
    git remote add origin "git@github.com:${GITHUB_USERNAME}/mikrotik-2fa-vpn.git"
    echo "✅ Remote добавлен: git@github.com:${GITHUB_USERNAME}/mikrotik-2fa-vpn.git"
fi

# Проверка статуса git
echo ""
echo "=========================================="
echo "Статус Git репозитория"
echo "=========================================="
echo ""

if [ ! -d ".git" ]; then
    echo "Инициализирую Git репозиторий..."
    git init
    git add .
    git commit -m "Initial commit: MikroTik 2FA VPN System

- Full backend with FastAPI (60+ API endpoints)
- React frontend with 9 complete pages
- Telegram bot integration
- MikroTik router integration (SSH + REST API)
- Complete documentation
- Automated installation scripts
- Internationalization (ru/en)
- Audit logs and statistics"
    git branch -M main
    echo "✅ Git репозиторий инициализирован и первый коммит создан"
else
    echo "Git репозиторий уже инициализирован"
    
    # Проверка наличия коммитов
    if ! git rev-parse HEAD >/dev/null 2>&1; then
        echo "Создаю первый коммит..."
        git add .
        git commit -m "Initial commit: MikroTik 2FA VPN System"
        git branch -M main
        echo "✅ Первый коммит создан"
    fi
fi

echo ""
echo "=========================================="
echo "✅ Все готово для публикации!"
echo "=========================================="
echo ""
echo "Следующие шаги:"
echo ""
echo "1. Создайте репозиторий на GitHub (если еще не создан):"
echo "   https://github.com/new"
echo "   Название: mikrotik-2fa-vpn"
echo "   ⚠️  НЕ ставьте галочки 'Add README', 'Add .gitignore', 'Choose license'"
echo ""
echo "2. Загрузите код на GitHub:"
echo "   cd $SCRIPT_DIR"
echo "   git push -u origin main"
echo ""
echo "3. Проверка статуса:"
echo "   git status"
echo ""
echo "=========================================="
