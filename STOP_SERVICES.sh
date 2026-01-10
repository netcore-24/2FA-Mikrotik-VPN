#!/bin/bash
# Скрипт для остановки всех сервисов проекта

echo "🛑 Остановка MikroTik 2FA VPN System..."

# Останавливаем backend
if [ -f /tmp/mikrotik-backend.pid ]; then
    PID=$(cat /tmp/mikrotik-backend.pid)
    if kill -0 $PID 2>/dev/null; then
        kill $PID
        echo "✅ Backend остановлен (PID: $PID)"
        rm /tmp/mikrotik-backend.pid
    else
        echo "⚠️  Backend не запущен (PID файл найден, но процесс не существует)"
        rm /tmp/mikrotik-backend.pid
    fi
else
    # Пробуем найти процесс по имени
    PID=$(pgrep -f "uvicorn backend.main:app" | head -1)
    if [ -n "$PID" ]; then
        kill $PID
        echo "✅ Backend остановлен (PID: $PID)"
    else
        echo "ℹ️  Backend не запущен"
    fi
fi

# Останавливаем Telegram бот
PID=$(pgrep -f "telegram_bot.bot" | head -1)
if [ -n "$PID" ]; then
    kill $PID
    echo "✅ Telegram бот остановлен (PID: $PID)"
else
    echo "ℹ️  Telegram бот не запущен"
fi

echo ""
echo "✅ Все сервисы остановлены!"
