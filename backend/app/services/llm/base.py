from abc import ABC, abstractmethod
from collections.abc import AsyncIterator


class EmbedProvider(ABC):
    @abstractmethod
    async def embed(self, text: str) -> list[float]:
        ...

    @abstractmethod
    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        ...


class ChatProvider(ABC):
    @abstractmethod
    async def chat(
        self,
        messages: list[dict],
        system_prompt: str,
        stream: bool = True,
    ) -> AsyncIterator[str]:
        ...


class LLMProvider(EmbedProvider, ChatProvider):
    """Combined provider for backends that support both embedding and chat."""

