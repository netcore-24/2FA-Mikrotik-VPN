"""
API endpoints для работы с интернационализацией.
"""
from fastapi import APIRouter, Depends, Request
from typing import Dict
from backend.api.i18n_dependencies import get_language, get_translate
from backend.utils.i18n import get_translations, SUPPORTED_LANGUAGES, DEFAULT_LANGUAGE

router = APIRouter(prefix="/i18n", tags=["i18n"])


@router.get("/languages")
async def get_supported_languages():
    """
    Получить список поддерживаемых языков.
    """
    return {
        "supported_languages": SUPPORTED_LANGUAGES,
        "default_language": DEFAULT_LANGUAGE,
    }


@router.get("/translations")
async def get_all_translations(
    request: Request,
    language: str = Depends(get_language),
):
    """
    Получить все переводы для указанного языка.
    Полезно для фронтенда - получить все переводы одним запросом.
    """
    translations = get_translations(language)
    return {
        "language": language,
        "translations": translations,
    }


@router.get("/translate/{key:path}")
async def translate_key(
    key: str,
    language: str = Depends(get_language),
    translate_func=Depends(get_translate),
):
    """
    Получить перевод конкретного ключа.
    
    Пример: /api/i18n/translate/auth.login.title
    """
    translated = translate_func(key)
    return {
        "key": key,
        "translation": translated,
        "language": language,
    }
