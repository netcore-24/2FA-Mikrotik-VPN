#!/bin/bash

# Скрипт для помощи в настройке GitHub репозитория
# Этот скрипт НЕ публикует код автоматически, а только помогает настроить git

set -e

echo "=========================================="
echo "Настройка Git для GitHub"
echo "=========================================="
echo ""

# Проверка наличия git
if ! command -v git &> /dev/null; then
    echo "❌ Git не установлен. Устанавливаю..."
    sudo apt update
    sudo apt install git -y
    echo "✅ Git установлен"
else
    echo "✅ Git уже установлен: $(git --version)"
fi

echo ""
echo "=========================================="
echo "Настройка Git пользователя"
echo "=========================================="

# Проверка текущей конфигурации
CURRENT_NAME=$(git config --global user.name || echo "")
CURRENT_EMAIL=$(git config --global user.email || echo "")

if [ -n "$CURRENT_NAME" ] && [ -n "$CURRENT_EMAIL" ]; then
    echo "Текущая конфигурация:"
    echo "  Имя: $CURRENT_NAME"
    echo "  Email: $CURRENT_EMAIL"
    read -p "Использовать текущую конфигурацию? (y/n) [y]: " USE_CURRENT
    USE_CURRENT=${USE_CURRENT:-y}
else
    USE_CURRENT="n"
fi

if [ "$USE_CURRENT" != "y" ]; then
    echo ""
    echo "Введите ваши данные для Git:"
    read -p "Ваше имя (для Git): " GIT_NAME
    read -p "Ваш email (для GitHub): " GIT_EMAIL
    
    git config --global user.name "$GIT_NAME"
    git config --global user.email "$GIT_EMAIL"
    echo "✅ Git настроен: $GIT_NAME <$GIT_EMAIL>"
else
    echo "✅ Используется текущая конфигурация"
fi

echo ""
echo "=========================================="
echo "Инициализация Git в проекте"
echo "=========================================="

# Переход в директорию проекта
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$SCRIPT_DIR"

cd "$PROJECT_DIR"

# Инициализация git, если еще не сделано
if [ ! -d ".git" ]; then
    echo "Инициализирую Git репозиторий..."
    git init
    echo "✅ Git репозиторий инициализирован"
else
    echo "✅ Git репозиторий уже инициализирован"
fi

# Проверка наличия изменений
if [ -n "$(git status --porcelain)" ]; then
    echo ""
    echo "Найдены изменения для коммита"
    echo ""
    read -p "Добавить все файлы и создать первый коммит? (y/n) [y]: " CREATE_COMMIT
    CREATE_COMMIT=${CREATE_COMMIT:-y}
    
    if [ "$CREATE_COMMIT" = "y" ]; then
        # Проверка наличия секретов
        echo ""
        echo "Проверка безопасности..."
        if [ -f ".env" ]; then
            echo "⚠️  ВНИМАНИЕ: Найден файл .env"
            echo "   Этот файл должен быть в .gitignore (и должен быть)"
            read -p "   Продолжить? (y/n) [n]: " CONTINUE
            CONTINUE=${CONTINUE:-n}
            if [ "$CONTINUE" != "y" ]; then
                echo "❌ Прервано пользователем"
                exit 1
            fi
        fi
        
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
        
        echo "✅ Первый коммит создан"
        
        # Переименование ветки в main
        CURRENT_BRANCH=$(git branch --show-current)
        if [ "$CURRENT_BRANCH" != "main" ]; then
            git branch -M main
            echo "✅ Ветка переименована в 'main'"
        fi
    fi
else
    echo "✅ Все изменения уже закоммичены"
    
    # Переименование ветки в main
    CURRENT_BRANCH=$(git branch --show-current 2>/dev/null || echo "")
    if [ -n "$CURRENT_BRANCH" ] && [ "$CURRENT_BRANCH" != "main" ]; then
        git branch -M main
        echo "✅ Ветка переименована в 'main'"
    fi
fi

echo ""
echo "=========================================="
echo "Настройка GitHub Remote"
echo "=========================================="

# Проверка существующего remote
if git remote | grep -q "^origin$"; then
    EXISTING_URL=$(git remote get-url origin)
    echo "Найден существующий remote 'origin': $EXISTING_URL"
    read -p "Изменить? (y/n) [n]: " CHANGE_REMOTE
    CHANGE_REMOTE=${CHANGE_REMOTE:-n}
    
    if [ "$CHANGE_REMOTE" = "y" ]; then
        git remote remove origin
    else
        echo "✅ Используется существующий remote"
        echo ""
        echo "=========================================="
        echo "Следующие шаги:"
        echo "=========================================="
        echo ""
        echo "1. Создайте Personal Access Token на GitHub:"
        echo "   GitHub → Settings → Developer settings → Personal access tokens"
        echo "   Generate new token (classic) → Выберите 'repo' → Generate"
        echo ""
        echo "2. Загрузите код на GitHub:"
        echo "   git push -u origin main"
        echo ""
        echo "   При запросе пароля используйте ваш Personal Access Token (не пароль!)"
        echo ""
        echo "Подробная инструкция: см. файл GITHUB_AUTH.md"
        exit 0
    fi
fi

echo ""
echo "Введите данные вашего GitHub репозитория:"
read -p "GitHub username: " GITHUB_USERNAME

# Выбор метода (HTTPS или SSH)
echo ""
echo "Выберите метод подключения:"
echo "1) HTTPS (рекомендуется для начинающих)"
echo "2) SSH (более безопасно, но нужно настроить SSH ключи)"
read -p "Ваш выбор [1]: " CONNECTION_METHOD
CONNECTION_METHOD=${CONNECTION_METHOD:-1}

if [ "$CONNECTION_METHOD" = "2" ]; then
    REMOTE_URL="git@github.com:${GITHUB_USERNAME}/mikrotik-2fa-vpn.git"
    echo ""
    echo "⚠️  Для SSH нужно:"
    echo "   1. Создать SSH ключ: ssh-keygen -t ed25519 -C 'ваш-email@example.com'"
    echo "   2. Добавить публичный ключ в GitHub: Settings → SSH and GPG keys"
    echo "   3. Проверить подключение: ssh -T git@github.com"
    echo ""
    read -p "SSH ключи уже настроены? (y/n) [n]: " SSH_READY
    SSH_READY=${SSH_READY:-n}
    
    if [ "$SSH_READY" != "y" ]; then
        echo "❌ Настройте SSH ключи сначала. См. GITHUB_AUTH.md для инструкции"
        exit 1
    fi
else
    REMOTE_URL="https://github.com/${GITHUB_USERNAME}/mikrotik-2fa-vpn.git"
fi

git remote add origin "$REMOTE_URL"
echo "✅ Remote 'origin' добавлен: $REMOTE_URL"

echo ""
echo "=========================================="
echo "Настройка Credential Helper"
echo "=========================================="

read -p "Сохранять токен локально для удобства? (y/n) [y]: " SAVE_CREDENTIALS
SAVE_CREDENTIALS=${SAVE_CREDENTIALS:-y}

if [ "$SAVE_CREDENTIALS" = "y" ]; then
    echo "Выберите метод сохранения:"
    echo "1) cache - кешировать на 1 час (более безопасно)"
    echo "2) store - сохранить навсегда (удобнее, но менее безопасно)"
    read -p "Ваш выбор [1]: " CREDENTIAL_METHOD
    CREDENTIAL_METHOD=${CREDENTIAL_METHOD:-1}
    
    if [ "$CREDENTIAL_METHOD" = "2" ]; then
        git config --global credential.helper store
        echo "✅ Credential helper настроен на 'store' (сохраняет навсегда)"
    else
        git config --global credential.helper 'cache --timeout=3600'
        echo "✅ Credential helper настроен на 'cache' (кеширует на 1 час)"
    fi
else
    echo "✅ Credential helper не настроен (будете вводить токен каждый раз)"
fi

echo ""
echo "=========================================="
echo "✅ Настройка завершена!"
echo "=========================================="
echo ""
echo "Следующие шаги:"
echo ""
echo "1. Создайте репозиторий на GitHub (если еще не создан):"
echo "   https://github.com/new"
echo "   Название: mikrotik-2fa-vpn"
echo "   ⚠️  НЕ ставьте галочки 'Add README', 'Add .gitignore', 'Choose license'"
echo ""
echo "2. Создайте Personal Access Token:"
echo "   GitHub → Settings → Developer settings → Personal access tokens"
echo "   Generate new token (classic) → Выберите 'repo' → Generate"
echo "   ⚠️  Скопируйте токен сразу! (начинается с ghp_)"
echo ""
echo "3. Загрузите код на GitHub:"
echo "   cd $PROJECT_DIR"
if [ "$CONNECTION_METHOD" = "2" ]; then
    echo "   git push -u origin main"
    echo "   (SSH не требует пароля, если ключи настроены)"
else
    echo "   git push -u origin main"
    echo "   Username: $GITHUB_USERNAME"
    echo "   Password: <ваш Personal Access Token> (не пароль!)"
fi
echo ""
echo "Подробная инструкция по аутентификации: см. файл GITHUB_AUTH.md"
echo ""
echo "=========================================="
