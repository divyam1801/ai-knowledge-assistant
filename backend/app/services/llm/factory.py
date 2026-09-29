from app.config import settings
from app.services.llm.base import LLMProvider
from app.services.llm.ollama import OllamaProvider

_provider: LLMProvider | None = None


def get_llm_provider() -> LLMProvider:
    global _provider
    if _provider is not None:
        return _provider

    match settings.llm_provider:
        case "ollama":
            _provider = OllamaProvider(
                base_url=settings.ollama_base_url,
                embed_model=settings.ollama_embed_model,
                chat_model=settings.ollama_chat_model,
            )
        case _:
            raise ValueError(f"Unknown LLM provider: {settings.llm_provider}")

    return _provider
