from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    DB_SCHEME: str | None = None
    DB_USER: str | None = None
    DB_PASSWORD: str | None = None
    DB_HOST: str | None = None
    DB_PORT: str | None = None
    DB_NAME: str | None = None

    # Lakehouse Access (Fabric OneLake, Bronze)
    LAKEHOUSE_WORKSPACE_ID: str | None = None
    LAKEHOUSE_ID: str | None = None
    LAKEHOUSE_STORAGE_ENDPOINT: str | None = None
    LAKEHOUSE_TABLES_PATH: str | None = None

    # Blob Storage (Azure Blob, invoice document access)
    BLOB_STORAGE_ACCOUNT_NAME: str | None = None
    BLOB_STORAGE_ENDPOINT: str | None = None
    BLOB_CONTAINER_NAME: str | None = None

    # Authentication - OIDC
    OIDC_METADATA_URL: str | None = None
    OIDC_CLIENT_ID: str | None = None
    OIDC_AUDIENCE: str | None = None
    OIDC_SCOPES: str | None = None
    OIDC_JWKS_CACHE_TTL_SECONDS: int = 3600

    # Authentication - Entra ID (App Registration, shared by SQL and Lakehouse access)
    AZURE_TENANT_ID: str | None = None
    AZURE_CLIENT_ID: str | None = None
    AZURE_CLIENT_SECRET: str | None = None
    # When true, authenticate with the AZURE_* app registration (client-credentials)
    # instead of the local `az login` session.
    AZURE_FLG_USE_APP_REGISTRATION: bool = False

    # Authentication - Microsoft Graph (public client app registration, delegated
    # permissions, device-code sign-in — separate app registration from the
    # AZURE_* one above, which is app-only/client-credentials for Lakehouse & SQL)
    GRAPH_TENANT_ID: str | None = None
    GRAPH_CLIENT_ID: str | None = None

    # Used for client-credentials auth (app-only) to read a shared mailbox - PRD
    # Not needed for tests using delegated auth
    GRAPH_CLIENT_SECRET: str | None = None
    GRAPH_MAILBOX: str | None = None

    # The payment-matching mailbox. Same app registration as above (one is
    # granted access to both mailboxes), so only the address differs; the
    # GRAPH_TENANT_ID/CLIENT_ID/CLIENT_SECRET trio is shared.
    PAYMENT_GRAPH_MAILBOX: str | None = None

    # LLM - Google Vertex AI service account (client's GCP project)
    GOOGLE_SA_TYPE: str | None = None
    GOOGLE_SA_PROJECT_ID: str | None = None
    GOOGLE_SA_PRIVATE_KEY_ID: str | None = None
    GOOGLE_SA_PRIVATE_KEY: str | None = None
    GOOGLE_SA_CLIENT_EMAIL: str | None = None
    GOOGLE_SA_CLIENT_ID: str | None = None
    GOOGLE_SA_AUTH_URI: str | None = None
    GOOGLE_SA_TOKEN_URI: str | None = None
    GOOGLE_SA_AUTH_PROVIDER_X509_CERT_URL: str | None = None
    GOOGLE_SA_CLIENT_X509_CERT_URL: str | None = None
    GOOGLE_SA_UNIVERSE_DOMAIN: str | None = None
    # Gemini 3 models are only served from "global"
    GOOGLE_LOCATION: str = "global"

    # LLM Behavior
    LLM_MODEL: str = "gemini-2.5-flash"
    LLM_TEMPERATURE: float = 0.0
    # Gemini counts thinking tokens against this cap
    LLM_MAX_TOKENS: int = 16000
    LLM_TIMEOUT: int = 150
    LLM_MAX_RETRIES: int = 4

    # Tracing (MLflow). Unset disables tracing entirely — see
    # `invoice_extraction.tracing`. Declared here because Settings rejects
    # unknown .env keys, so an undeclared one would break app startup.
    MLFLOW_TRACKING_URI: str | None = None

    # Notifications
    TREASURY_EMAIL: str | None = None

    class Config:
        env_file = str(Path(__file__).parent.parent.parent / ".env")
        case_sensitive = False


settings = Settings()
