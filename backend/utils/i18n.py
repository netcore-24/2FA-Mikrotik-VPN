"""
Система интернационализации (i18n) для приложения.
"""
import json
import os
from typing import Dict, Optional
from pathlib import Path
from fastapi import Request

# Поддерживаемые языки
SUPPORTED_LANGUAGES = ["ru", "en"]
DEFAULT_LANGUAGE = "ru"

# Кэш для переводов
_translations_cache: Dict[str, Dict[str, str]] = {}


def get_locales_dir() -> Path:
    """Получить путь к директории с переводами."""
    # Определяем корневую директорию проекта (на 2 уровня выше от backend/utils)
    project_root = Path(__file__).parent.parent.parent
    return project_root / "locales"


def load_translations(language: str) -> Dict[str, str]:
    """
    Загрузить переводы для указанного языка.
    Использует кэш для оптимизации.
    """
    if language not in SUPPORTED_LANGUAGES:
        language = DEFAULT_LANGUAGE
    
    # Проверяем кэш
    if language in _translations_cache:
        return _translations_cache[language]
    
    # Загружаем переводы из JSON файла
    locales_dir = get_locales_dir()
    translation_file = locales_dir / language / "messages.json"
    
    if not translation_file.exists():
        # Если файл не найден, используем язык по умолчанию
        if language != DEFAULT_LANGUAGE:
            return load_translations(DEFAULT_LANGUAGE)
        return {}
    
    try:
        with open(translation_file, "r", encoding="utf-8") as f:
            translations = json.load(f)
            _translations_cache[language] = translations
            return translations
    except (json.JSONDecodeError, IOError):
        return {}


def get_language_from_request(request: Request, default: Optional[str] = None) -> str:
    """
    Определить язык из запроса.
    Проверяет заголовок Accept-Language и параметр ?lang=.
    """
    # Проверяем параметр запроса
    lang_param = request.query_params.get("lang")
    if lang_param and lang_param in SUPPORTED_LANGUAGES:
        return lang_param
    
    # Проверяем заголовок Accept-Language
    accept_language = request.headers.get("Accept-Language", "")
    if accept_language:
        # Парсим Accept-Language (формат: "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7")
        for lang_part in accept_language.split(","):
            lang_code = lang_part.split(";")[0].strip().lower()
            # Берем первые 2 символа (язык без региона)
            lang_code_short = lang_code.split("-")[0]
            if lang_code_short in SUPPORTED_LANGUAGES:
                return lang_code_short
    
    # Используем язык по умолчанию из настроек или переданный параметр
    if default and default in SUPPORTED_LANGUAGES:
        return default
    
    return DEFAULT_LANGUAGE


def translate(key: str, language: str = DEFAULT_LANGUAGE, **kwargs) -> str:
    """
    Получить перевод по ключу.
    
    Args:
        key: Ключ перевода (например, "auth.login.title")
        language: Код языка (ru, en)
        **kwargs: Параметры для подстановки в строку
    
    Returns:
        Переведенная строка или сам ключ, если перевод не найден
    """
    translations = load_translations(language)
    
    # Поддерживаем вложенные ключи через точку
    value = translations
    for part in key.split("."):
        if isinstance(value, dict) and part in value:
            value = value[part]
        else:
            # Если ключ не найден, возвращаем ключ
            return key
    
    # Если значение - строка, подставляем параметры
    if isinstance(value, str) and kwargs:
        try:
            return value.format(**kwargs)
        except (KeyError, ValueError):
            return value
    
    return value if isinstance(value, str) else key


def get_translations(language: str) -> Dict[str, str]:
    """
    Получить все переводы для указанного языка.
    Полезно для отправки всех переводов на фронтенд.
    """
    return load_translations(language)


def clear_cache():
    """Очистить кэш переводов (полезно при разработке)."""
    global _translations_cache
    _translations_cache.clear()
