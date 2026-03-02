from pydantic import Secret
from pydantic_settings import BaseSettings, SettingsConfigDict

from api.util.fs import ROOT_DIR


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ROOT_DIR / '.env',
        env_file_encoding='utf-8',
        extra='ignore',
    )

    OAI_PROXY_HOST: str = '127.0.0.1'
    OAI_PROXY_PORT: int = 8084
    OAI_PROXY_WORKERS: int = 1
    # Upstream OpenAI-compatible API base URL (e.g. https://api.openai.com)
    OAI_PROXY_OPENAI_BASE_URL: str = 'https://api.openai.com'
    OAI_PROXY_AES_KEY: Secret[str]
    # Static key: when "Bearer STATIC" is used, this key is sent upstream.
    # When OAI_PROXY_STATIC_BASE_URL is set, static requests go to that base (e.g. Azure).
    OAI_PROXY_STATIC_KEY: Secret[str] | None = None
    OAI_PROXY_STATIC_BASE_URL: str | None = None  # e.g. https://YOUR_RESOURCE.openai.azure.com/openai
    OAI_PROXY_STATIC_API_VERSION: str | None = None  # e.g. 2025-04-01-preview for Azure


settings = Settings()  # type: ignore[missing-argument]
