"""
Clean LLM Factory for creating chat models.
Uses Google Vertex AI (Gemini), authenticated with a service account.
"""

from typing import Type

from google.oauth2 import service_account
from langchain_core.language_models import BaseChatModel
from langchain_core.runnables import Runnable
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel

SCOPES = ["https://www.googleapis.com/auth/cloud-platform"]

# Service-account JSON keys, read from `settings.GOOGLE_SA_<KEY>`
SERVICE_ACCOUNT_KEYS = (
    "type",
    "project_id",
    "private_key_id",
    "private_key",
    "client_email",
    "client_id",
    "auth_uri",
    "token_uri",
    "auth_provider_x509_cert_url",
    "client_x509_cert_url",
    "universe_domain",
)


def service_account_info(settings) -> dict[str, str]:
    """Build the service-account JSON dict from the GOOGLE_SA_* settings."""
    info: dict[str, str] = {}
    for key in SERVICE_ACCOUNT_KEYS:
        value = getattr(settings, f"GOOGLE_SA_{key.upper()}", None)
        if not value:
            raise KeyError(f"Missing required setting: GOOGLE_SA_{key.upper()}")
        info[key] = value

    # Env stores the key body only, with escaped newlines
    body = info["private_key"].replace("\\n", "\n").strip()
    if not body.startswith("-----BEGIN"):
        body = f"-----BEGIN PRIVATE KEY-----\n{body}\n-----END PRIVATE KEY-----"
    info["private_key"] = f"{body}\n"
    return info


class LLMFactory:
    """
    Factory for creating LLM instances with standardized configuration.

    Usage:
        # From settings
        factory = LLMFactory.from_settings(settings)

        # Direct instantiation
        factory = LLMFactory(
            credentials=creds,
            project="my-gcp-project",
            model="gemini-2.5-flash",
        )

        # Create models
        chat_model = factory.create_chat_model()
        structured_llm = factory.create_structured_llm(MySchema)
    """

    def __init__(
        self,
        credentials: service_account.Credentials | None = None,
        project: str | None = None,
        location: str = "global",
        model: str | None = None,
        temperature: float = 0.0,
        max_tokens: int = 16000,
        timeout: int = 60,
        max_retries: int = 4,
    ):
        self.credentials = credentials
        self.project = project
        self.location = location
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout
        self.max_retries = max_retries

    @classmethod
    def from_settings(cls, settings) -> "LLMFactory":
        """
        Create factory from settings object.

        Args:
            settings: Settings object with LLM configuration fields

        Returns:
            Configured LLMFactory instance

        Example:
            >>> from config.settings import settings
            >>> factory = LLMFactory.from_settings(settings)
            >>> chat_model = factory.create_chat_model()
        """
        info = service_account_info(settings)
        credentials = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
        return cls(
            credentials=credentials,
            project=info["project_id"],
            location=settings.GOOGLE_LOCATION,
            model=settings.LLM_MODEL,
            temperature=settings.LLM_TEMPERATURE,
            max_tokens=settings.LLM_MAX_TOKENS,
            timeout=settings.LLM_TIMEOUT,
            max_retries=settings.LLM_MAX_RETRIES,
        )

    def create_chat_model(
        self,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        streaming: bool = False,
        **kwargs,
    ) -> BaseChatModel:
        """
        Create a chat model instance.
        """
        model = model or self.model
        temperature = temperature if temperature is not None else self.temperature
        max_tokens = max_tokens or self.max_tokens

        return ChatGoogleGenerativeAI(
            model=model,
            vertexai=True,
            project=self.project,
            location=self.location,
            credentials=self.credentials,
            temperature=temperature,
            max_output_tokens=max_tokens,
            timeout=self.timeout,
            max_retries=self.max_retries,
            streaming=streaming,
            **kwargs,
        )

    def create_structured_llm(
        self,
        output_schema: Type[BaseModel],
        model: str | None = None,
        temperature: float | None = None,
        **kwargs,
    ) -> Runnable:
        """
        Create a chat model with structured output.

        Args:
            output_schema: Pydantic model defining the output structure
            model: Model name (uses default if not provided)
            temperature: Sampling temperature (uses default if not provided)
            **kwargs: Additional arguments for the chat model

        Returns:
            Chat model configured for structured output
        """
        chat_model = self.create_chat_model(
            model=model,
            temperature=temperature,
            **kwargs,
        )
        return chat_model.with_structured_output(output_schema)
