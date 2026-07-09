from typing import Optional
from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    DB_SCHEME: Optional[str] = None
    DB_USER: Optional[str] = None
    DB_PASSWORD: Optional[str] = None
    DB_HOST: Optional[str] = None
    DB_PORT: Optional[str] = None
    DB_NAME: Optional[str] = None

    # Authentication - API Keys
    HASHED_API_KEY: Optional[str] = None

    # Authentication - OIDC
    OIDC_METADATA_URL: Optional[str] = None
    OIDC_CLIENT_ID: Optional[str] = None
    OIDC_AUDIENCE: Optional[str] = None
    OIDC_SCOPES: Optional[str] = None

    # LLM license credentials
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_API_BASE: Optional[str] = None
    OPENAI_MODEL: Optional[str] = None
    EMBEDDINGS_MODEL: Optional[str] = None

    # LLM Behavior
    LLM_TEMPERATURE: float = 0.0
    LLM_MAX_TOKENS: int = 4000
    LLM_TIMEOUT: int = 150

    class Config:
        env_file = str(Path(__file__).parent.parent.parent / ".env")
        case_sensitive = False


settings = Settings()
