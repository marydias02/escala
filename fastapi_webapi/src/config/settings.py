from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    DB_SCHEME: Optional[str] = None
    DB_USER: Optional[str] = None
    DB_PASSWORD: Optional[str] = None
    DB_HOST: Optional[str] = None
    DB_PORT: Optional[str] = None
    DB_NAME: Optional[str] = None

    # Lakehouse Access (Fabric OneLake, Bronze)
    LAKEHOUSE_WORKSPACE_ID: Optional[str] = None
    LAKEHOUSE_ID: Optional[str] = None
    LAKEHOUSE_STORAGE_ENDPOINT: Optional[str] = None
    LAKEHOUSE_TABLES_PATH: Optional[str] = None

    # Authentication - API Keys
    HASHED_API_KEY: Optional[str] = None

    # Authentication - OIDC
    OIDC_METADATA_URL: Optional[str] = None
    OIDC_CLIENT_ID: Optional[str] = None
    OIDC_AUDIENCE: Optional[str] = None
    OIDC_SCOPES: Optional[str] = None

    # Authentication - Entra ID (App Registration, shared by SQL and Lakehouse access)
    AZURE_TENANT_ID: Optional[str] = None
    AZURE_CLIENT_ID: Optional[str] = None
    AZURE_CLIENT_SECRET: Optional[str] = None

    # Authentication - Microsoft Graph (public client app registration, delegated
    # permissions, device-code sign-in — separate app registration from the
    # AZURE_* one above, which is app-only/client-credentials for Lakehouse & SQL)
    GRAPH_TENANT_ID: Optional[str] = None
    GRAPH_CLIENT_ID: Optional[str] = None

    # LLM license credentials
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_API_BASE: Optional[str] = None
    OPENAI_MODEL: Optional[str] = None
    EMBEDDINGS_MODEL: Optional[str] = None

    # LLM Behavior
    LLM_TEMPERATURE: float = 0.0
    LLM_MAX_TOKENS: int = 4000
    LLM_TIMEOUT: int = 150

    # Tracing (MLflow). Unset disables tracing entirely — see
    # `invoice_extraction.tracing`. Declared here because Settings rejects
    # unknown .env keys, so an undeclared one would break app startup.
    MLFLOW_TRACKING_URI: Optional[str] = None

    class Config:
        env_file = str(Path(__file__).parent.parent.parent / ".env")
        case_sensitive = False


settings = Settings()
