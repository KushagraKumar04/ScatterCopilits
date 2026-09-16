from fastapi import Header
from typing import Optional

from .services.ai_client import AISettings, settings_from_env


def get_ai_settings(
    x_ai_provider: Optional[str] = Header(default=None),
    x_ai_key: Optional[str] = Header(default=None),
    x_ai_model: Optional[str] = Header(default=None),
    x_ai_base_url: Optional[str] = Header(default=None),
    x_ai_language: Optional[str] = Header(default=None),
) -> AISettings:
    env = settings_from_env()
    return AISettings(
        provider=(x_ai_provider or env.provider),
        api_key=(x_ai_key or env.api_key),
        model=(x_ai_model or env.model),
        base_url=(x_ai_base_url or env.base_url),
        language=(x_ai_language or env.language),
    )
