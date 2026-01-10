"""
Dependencies для работы с интернационализацией.
"""
from fastapi import Request, Depends
from backend.utils.i18n import get_language_from_request, translate, SUPPORTED_LANGUAGES, DEFAULT_LANGUAGE
from config.settings import settings


def get_language(request: Request) -> str:
    """
    Dependency для получения языка из запроса.
    Использует язык из настроек по умолчанию, если не указан в запросе.
    """
    default_lang = getattr(settings, "LANGUAGE", DEFAULT_LANGUAGE)
    return get_language_from_request(request, default=default_lang)


def get_translate(language: str = Depends(get_language)):
    """
    Dependency для получения функции перевода с уже установленным языком.
    """
    def translate_with_lang(key: str, **kwargs) -> str:
        return translate(key, language=language, **kwargs)
    
    return translate_with_lang
