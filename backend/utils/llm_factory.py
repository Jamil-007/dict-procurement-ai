from config import settings
from langchain_core.language_models.chat_models import BaseChatModel


def get_llm() -> BaseChatModel:
    """
    Returns configured LLM instance based on settings.LLM_PROVIDER.

    Returns:
        BaseChatModel: Configured LLM instance (ChatVertexAI or ChatAnthropic)

    Raises:
        ValueError: If LLM_PROVIDER is not recognized or required credentials are missing
    """
    if settings.LLM_PROVIDER == "vertex_ai":
        if not settings.GOOGLE_CLOUD_PROJECT:
            raise ValueError("GOOGLE_CLOUD_PROJECT must be set for Vertex AI provider")

        try:
            # Try newer langchain-google-genai package first
            from langchain_google_genai import ChatGoogleGenerativeAI
            return ChatGoogleGenerativeAI(
                model=settings.VERTEX_MODEL_NAME,
                google_api_key=None,  # Uses Application Default Credentials
                temperature=settings.TEMPERATURE
            )
        except ImportError:
            # Fallback to langchain-google-vertexai (deprecated but still works)
            from langchain_google_vertexai import ChatVertexAI
            return ChatVertexAI(
                model_name=settings.VERTEX_MODEL_NAME,
                project=settings.GOOGLE_CLOUD_PROJECT,
                location=settings.GOOGLE_CLOUD_LOCATION,
                temperature=settings.TEMPERATURE
            )

    elif settings.LLM_PROVIDER == "anthropic":
        if not settings.ANTHROPIC_API_KEY:
            raise ValueError("ANTHROPIC_API_KEY must be set for Anthropic provider")

        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(
            model=settings.ANTHROPIC_MODEL_NAME,
            anthropic_api_key=settings.ANTHROPIC_API_KEY,
            temperature=settings.TEMPERATURE
        )

    else:
        raise ValueError(f"Unknown LLM provider: {settings.LLM_PROVIDER}")


def get_llm_info() -> dict:
    """Returns information about the configured LLM provider."""
    return {
        "provider": settings.LLM_PROVIDER,
        "model": settings.VERTEX_MODEL_NAME if settings.LLM_PROVIDER == "vertex_ai" else settings.ANTHROPIC_MODEL_NAME,
        "temperature": settings.TEMPERATURE
    }
