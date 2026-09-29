from abc import ABC, abstractmethod
from collections.abc import AsyncIterator


class LLMProvider(ABC):
    @abstractmethod
    async def embed(self, text: str) -> list[float]:
        ...

    @abstractmethod
    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        ...

    @abstractmethod
    async def chat(
        self,
        messages: list[dict],
        context: str,
        stream: bool = True,
    ) -> AsyncIterator[str]:
        ...

    @abstractmethod
    async def summarize(self, text: str) -> str:
        ...
