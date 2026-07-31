"""
Clean LLM Factory for creating chat models and embeddings.
Supports both OpenAI with automatic provider detection.
"""

from langchain_core.embeddings import Embeddings
from langchain_core.language_models import BaseChatModel
from langchain_openai import (
    ChatOpenAI,
    OpenAIEmbeddings,
)
from pydantic import BaseModel
from typing import Optional, Type


class LLMFactory:
    """
    Factory for creating LLM instances with standardized configuration.

    Usage:
        # From settings
        factory = LLMFactory.from_settings(settings)

        # Direct instantiation
        factory = LLMFactory(
            use_azure=False,
            openai_api_key="sk-...",
            openai_model="gpt-5-mini"
        )

        # Create models
        chat_model = factory.create_chat_model()
        embeddings = factory.create_embeddings()
        structured_llm = factory.create_structured_llm(MySchema)
    """

    def __init__(
        self,
        openai_api_key: Optional[str] = None,
        openai_api_base: Optional[str] = None,
        openai_model: str = None,
        embeddings_model: str = None,
        temperature: float = 0.0,
        max_tokens: int = 4000,
        timeout: int = 60,
    ):
        self.openai_api_key = openai_api_key
        self.openai_api_base = openai_api_base
        self.openai_model = openai_model
        self.embeddings_model = embeddings_model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout

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
        return cls(
            openai_api_key=settings.OPENAI_API_KEY,
            openai_api_base=settings.OPENAI_API_BASE,
            openai_model=settings.OPENAI_MODEL,
            embeddings_model=settings.EMBEDDINGS_MODEL,
            temperature=settings.LLM_TEMPERATURE,
            max_tokens=settings.LLM_MAX_TOKENS,
            timeout=settings.LLM_TIMEOUT,
        )

    def create_chat_model(
        self,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        streaming: bool = False,
        **kwargs,
    ) -> BaseChatModel:
        """
        Create a chat model instance.
        """
        model = model or self.openai_model
        temperature = temperature if temperature is not None else self.temperature
        max_tokens = max_tokens or self.max_tokens

        return ChatOpenAI(
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=self.timeout,
            api_key=self.openai_api_key,
            base_url=self.openai_api_base,
            streaming=streaming,
            **kwargs,
        )

    def create_embeddings(
        self,
        model: Optional[str] = None,
    ) -> Embeddings:
        """
        Create an embeddings model instance.

        Args:
            model: Embeddings model name (uses default if not provided)

        Returns:
            OpenAIEmbeddings 
        Example:
            >>> embeddings = factory.create_embeddings()
            >>> vectors = await embeddings.aembed_documents(["Hello", "World"])
        """
        model = model or self.embeddings_model

        return OpenAIEmbeddings(
            model=model,
            api_key=self.openai_api_key,
            base_url=self.openai_api_base,
        )

    def create_structured_llm(
        self,
        output_schema: Type[BaseModel],
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        **kwargs,
    ) -> BaseChatModel:
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
        return chat_model.with_structured_output(output_schema, method="function_calling")
