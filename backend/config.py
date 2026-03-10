"""
Configuration management for the NLP Email Assistant.
Reads settings from environment variables / .env file.
"""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application-wide settings loaded from the environment."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # OpenAI
    openai_api_key: str = ""

    # Gmail
    email_address: str = "your_email@gmail.com"
    google_credentials_file: str = "credentials.json"

    # Server
    host: str = "0.0.0.0"
    port: int = 8000

    # App
    secret_key: str = ""
    debug: bool = True


settings = Settings()
