from app.config import settings
from app.services.llm.base import ChatProvider, EmbedProvider

_embed_provider: EmbedProvider | None = None
_chat_provider: ChatProvider | None = None


def _create_provider(name: str) -> EmbedProvider | ChatProvider:
    match name:
        case "ollama":
            from app.services.llm.ollama import OllamaProvider

            return OllamaProvider(
                base_url=settings.ollama_base_url,
                embed_model=settings.ollama_embed_model,
                chat_model=settings.ollama_chat_model,
            )
        case "gemini":
            from app.services.llm.gemini import GeminiProvider

            if not settings.gateway_api_key and not settings.gemini_api_key:
                raise ValueError("GATEWAY_API_KEY or GEMINI_API_KEY is required when using the gemini provider")
            return GeminiProvider(
                api_key=settings.gemini_api_key,
                embed_model=settings.gemini_embed_model,
                chat_model=settings.gemini_chat_model,
                gateway_base_url=settings.gateway_base_url,
                gateway_api_key=settings.gateway_api_key,
            )
        case _:
            raise ValueError(f"Unknown LLM provider: {name}")


def get_embed_provider() -> EmbedProvider:
    global _embed_provider
    if _embed_provider is None:
        name = settings.embed_provider or settings.llm_provider
        _embed_provider = _create_provider(name)
    return _embed_provider


def get_chat_provider() -> ChatProvider:
    global _chat_provider
    if _chat_provider is None:
        name = settings.chat_provider or settings.llm_provider
        _chat_provider = _create_provider(name)
    return _chat_provider
