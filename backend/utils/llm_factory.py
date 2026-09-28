from config import settings
from langchain_core.language_models.chat_models import BaseChatModel


def _thinking_budget() -> int | None:
    """
    The configured Gemini thinking budget, or None to leave the model's default.

    None and 0 are different answers: 0 turns thinking off, None hands the
    decision back to the model, which for the 2.5 family means a dynamic budget
    that runs the review prompts about four times slower.
    """
    budget = settings.GEMINI_THINKING_BUDGET
    return None if budget < 0 else budget


def get_llm(temperature: float | None = None) -> BaseChatModel:
    """
    Returns configured LLM instance based on settings.LLM_PROVIDER.

    Args:
        temperature: Optional temperature override. If None, uses settings.TEMPERATURE.

    Returns:
        BaseChatModel: Configured LLM instance (ChatVertexAI or ChatAnthropic)

    Raises:
        ValueError: If LLM_PROVIDER is not recognized or required credentials are missing
    """
    temp = temperature if temperature is not None else settings.TEMPERATURE

    if settings.LLM_PROVIDER == "vertex_ai":
        if not settings.GOOGLE_CLOUD_PROJECT:
            raise ValueError("GOOGLE_CLOUD_PROJECT must be set for Vertex AI provider")

        # Vertex AI authenticates via Application Default Credentials (on Cloud Run,
        # the service account with roles/aiplatform.user). Use ChatVertexAI for this:
        # ChatGoogleGenerativeAI is the Gemini *Developer API* client and requires an
        # explicit API key, so it cannot serve the vertex_ai path.
        from langchain_google_vertexai import ChatVertexAI

        return ChatVertexAI(
            model=settings.VERTEX_MODEL_NAME,
            project=settings.GOOGLE_CLOUD_PROJECT,
            location=settings.GOOGLE_CLOUD_LOCATION,
            temperature=temp,
        )

    elif settings.LLM_PROVIDER == "google_genai":
        if not settings.GOOGLE_API_KEY:
            raise ValueError("GOOGLE_API_KEY must be set for Google AI Studio provider")

        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI(
            model=settings.GEMINI_MODEL_NAME,
            google_api_key=settings.GOOGLE_API_KEY,
            temperature=temp,
            thinking_budget=_thinking_budget(),
        )

    elif settings.LLM_PROVIDER == "anthropic":
        if not settings.ANTHROPIC_API_KEY:
            raise ValueError("ANTHROPIC_API_KEY must be set for Anthropic provider")

        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(
            model=settings.ANTHROPIC_MODEL_NAME,
            anthropic_api_key=settings.ANTHROPIC_API_KEY,
            temperature=temp,
        )

    else:
        raise ValueError(f"Unknown LLM provider: {settings.LLM_PROVIDER}")


def get_llm_info() -> dict:
    """Returns information about the configured LLM provider."""
    info = {
        "provider": settings.LLM_PROVIDER,
        "model": {
            "vertex_ai": settings.VERTEX_MODEL_NAME,
            "google_genai": settings.GEMINI_MODEL_NAME,
        }.get(settings.LLM_PROVIDER, settings.ANTHROPIC_MODEL_NAME),
        "temperature": settings.TEMPERATURE,
    }
    # Only meaningful for Gemini, and worth surfacing on /health: a review that
    # suddenly got slow is usually this having reverted to the model default.
    if settings.LLM_PROVIDER in ("vertex_ai", "google_genai"):
        info["thinking_budget"] = settings.GEMINI_THINKING_BUDGET
    return info
