# Frontend - MikroTik 2FA VPN System

Веб-интерфейс администратора для управления системой.

## Технологии

- **React 18** - UI библиотека
- **React Router** - маршрутизация
- **React Query** - управление состоянием сервера
- **Zustand** - управление локальным состоянием
- **Axios** - HTTP клиент
- **Vite** - сборщик и dev сервер
- **CSS Modules** - стилизация

## Установка

```bash
cd frontend
npm install
```

## Разработка

```bash
npm run dev
```

Приложение будет доступно на http://localhost:5173

## Сборка для продакшена

```bash
npm run build
```

Собранные файлы будут в директории `dist/`

## Структура проекта

```
src/
├── components/      # Переиспользуемые компоненты
├── pages/          # Страницы приложения
├── services/       # API сервисы
├── store/          # Zustand stores
├── App.jsx         # Главный компонент
└── main.jsx        # Точка входа
```

## Основные страницы

- `/login` - Страница входа
- `/` - Дашборд
- `/users` - Управление пользователями
- `/registration-requests` - Заявки на регистрацию
- `/vpn-sessions` - VPN сессии
- `/mikrotik` - Управление MikroTik
- `/stats` - Статистика
- `/audit-logs` - Журнал аудита
- `/settings` - Настройки
