# Интернационализация (i18n) - Краткое руководство

## Быстрый старт

### Получение переводов на фронтенде

```javascript
// Получить все переводы для языка
const response = await fetch('/api/i18n/translations?lang=ru');
const { language, translations } = await response.json();

// Использовать перевод
const title = translations.auth.login.title; // "Вход в систему"
```

### Изменение языка в запросе

1. **Через параметр URL**: `/api/auth/login?lang=en`
2. **Через заголовок HTTP**: `Accept-Language: en,ru;q=0.9`

### Использование в Python коде (Backend)

```python
from backend.utils.i18n import translate

# Простой перевод
message = translate("auth.login.title", language="ru")

# Перевод с параметрами
message = translate("validation.min_length", language="en", min_length=8)
```

### Использование в FastAPI endpoints

```python
from fastapi import Depends
from backend.api.i18n_dependencies import get_translate

@router.get("/example")
async def example(t=Depends(get_translate)):
    return {"message": t("auth.login.title")}
```

## Доступные ключи переводов

### Аутентификация
- `auth.login.title` - "Вход в систему" / "Login"
- `auth.login.invalid_credentials` - Сообщение об ошибке
- `auth.logout.success` - Сообщение об успешном выходе
- `auth.token.invalid` - Недействительный токен

### Пользователи
- `user.not_found` - Пользователь не найден
- `user.created` - Пользователь создан
- `user.updated` - Пользователь обновлен

### VPN
- `vpn.session.created` - Сессия создана
- `vpn.connection.requested` - Запрос отправлен

Полный список доступен в файлах `locales/ru/messages.json` и `locales/en/messages.json`.

## Примеры использования

### Пример 1: Изменение языка в запросе

```bash
# Русский язык (по умолчанию)
curl http://localhost:8000/api/i18n/translations

# Английский язык
curl http://localhost:8000/api/i18n/translations?lang=en
```

### Пример 2: Получение конкретного перевода

```bash
curl http://localhost:8000/api/i18n/translate/auth.login.title?lang=en
# {"key": "auth.login.title", "translation": "Login", "language": "en"}
```

### Пример 3: Использование в endpoint

```python
@router.post("/example")
async def example_endpoint(
    request: Request,
    t=Depends(get_translate),
):
    return {
        "message": t("success.operation"),
        "error": t("error.not_found"),
    }
```

## Подробная документация

См. `docs/i18n.md` для полной документации.
