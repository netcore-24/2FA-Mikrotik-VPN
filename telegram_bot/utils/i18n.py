"""
Утилиты для интернационализации в Telegram боте.
"""
import json
import os
from typing import Optional
from pathlib import Path

# Кэш переводов
_translations_cache = {}


def _load_translations(language: str) -> dict:
    """Загрузить переводы для указанного языка."""
    if language in _translations_cache:
        return _translations_cache[language]
    
    # Определяем путь к файлу переводов
    project_root = Path(__file__).parent.parent.parent
    locales_path = project_root / "locales" / language / "messages.json"
    
    if not locales_path.exists():
        # Если файл не найден, используем русский по умолчанию
        if language != "ru":
            return _load_translations("ru")
        return {}
    
    try:
        with open(locales_path, "r", encoding="utf-8") as f:
            translations = json.load(f)
        _translations_cache[language] = translations
        return translations
    except Exception:
        return {}


def get_user_language(user_id: Optional[int] = None) -> str:
    """
    Определить язык пользователя.
    TODO: В будущем сохранять предпочтения пользователя в БД.
    """
    # По умолчанию русский, можно добавить логику определения языка
    return "ru"


def get_translation(language: str = 'ru'):
    """Получить функцию перевода для указанного языка."""
    translations = _load_translations(language)
    
    def translate(key: str, **kwargs) -> str:
        """Перевести ключ."""
        value = translations
        for part in key.split("."):
            if isinstance(value, dict):
                value = value.get(part)
                if value is None:
                    if language != "ru":
                        return get_translation("ru")(key, **kwargs)
                    return key
            else:
                if language != "ru":
                    return get_translation("ru")(key, **kwargs)
                return key
        
        if isinstance(value, str):
            # В messages.json переводы часто содержат литералы "\\n"
            value = value.replace("\\n", "\n")
            if kwargs:
                try:
                    return value.format(**kwargs)
                except (KeyError, ValueError):
                    return value
            return value
        return key
    
    return translate


def translate(key: str, user_id: Optional[int] = None, language: Optional[str] = None, **kwargs) -> str:
    """
    Перевести ключ на язык пользователя.
    
    Args:
        key: Ключ перевода (может быть вложенным, например "bot.start.welcome")
        user_id: ID пользователя Telegram (для определения языка)
        language: Явно указанный язык
        **kwargs: Параметры для форматирования строки
    
    Returns:
        Переведенная строка или ключ, если перевод не найден
    """
    # Определяем язык
    if language:
        lang = language
    elif user_id:
        lang = get_user_language(user_id)
    else:
        lang = "ru"  # По умолчанию
    
    # Загружаем переводы
    translations = _load_translations(lang)
    
    # Получаем значение по вложенному ключу
    value = translations
    for part in key.split("."):
        if isinstance(value, dict):
            value = value.get(part)
            if value is None:
                # Если перевод не найден, пробуем русский
                if lang != "ru":
                    return translate(key, language="ru", **kwargs)
                # Если и в русском нет, возвращаем ключ
                return key
        else:
            if lang != "ru":
                return translate(key, language="ru", **kwargs)
            return key
    
    # Форматируем строку, если есть параметры
    if isinstance(value, str):
        # В messages.json переводы часто содержат литералы "\\n"
        value = value.replace("\\n", "\n")
        if kwargs:
            try:
                return value.format(**kwargs)
            except (KeyError, ValueError):
                return value
        return value
    return key
