#!/bin/bash
# Скрипт для запуска всех сервисов проекта

cd /root/mikrotik-2fa-vpn

echo "🚀 Запуск MikroTik 2FA VPN System..."

# Активируем виртуальное окружение
source venv/bin/activate

# Проверяем, не запущен ли уже backend
if pgrep -f "uvicorn backend.main:app" > /dev/null; then
    echo "⚠️  Backend уже запущен (PID: $(pgrep -f 'uvicorn backend.main:app'))"
    echo "Для перезапуска сначала остановите: pkill -f 'uvicorn backend.main:app'"
else
    echo "📦 Запуск backend..."
    mkdir -p logs
    nohup uvicorn backend.main:app --host 0.0.0.0 --port 8000 > logs/backend.log 2>&1 &
    echo $! > /tmp/mikrotik-backend.pid
    sleep 2
    if pgrep -f "uvicorn backend.main:app" > /dev/null; then
        echo "✅ Backend запущен (PID: $(cat /tmp/mikrotik-backend.pid))"
        echo "   URL: http://localhost:8000"
        echo "   Логи: tail -f logs/backend.log"
    else
        echo "❌ Ошибка запуска backend. Проверьте логи: tail -f logs/backend.log"
        exit 1
    fi
fi

echo ""
echo "✅ Все сервисы запущены!"
echo ""
echo "📝 Для запуска Telegram бота:"
echo "   ./scripts/start_bot.sh"
