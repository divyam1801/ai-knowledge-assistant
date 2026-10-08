import json
import logging
import time
from collections.abc import AsyncIterator

import httpx

from app.services.llm.base import LLMProvider

logger = logging.getLogger("app.ollama")
EMBED_BATCH_SIZE = 32


class OllamaProvider(LLMProvider):
    def __init__(self, base_url: str, embed_model: str, chat_model: str):
        self.base_url = base_url.rstrip("/")
        self.embed_model = embed_model
        self.chat_model = chat_model

    async def embed(self, text: str) -> list[float]:
        t0 = time.perf_counter()
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                f"{self.base_url}/api/embeddings",
                json={"model": self.embed_model, "prompt": text},
            )
            response.raise_for_status()
            logger.info("[EMBED] single text — %.0fms", (time.perf_counter() - t0) * 1000)
            return response.json()["embedding"]

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        t0 = time.perf_counter()
        results: list[list[float]] = []
        for i in range(0, len(texts), EMBED_BATCH_SIZE):
            batch = texts[i : i + EMBED_BATCH_SIZE]
            async with httpx.AsyncClient(timeout=120) as client:
                for text in batch:
                    response = await client.post(
                        f"{self.base_url}/api/embeddings",
                        json={"model": self.embed_model, "prompt": text},
                    )
                    response.raise_for_status()
                    results.append(response.json()["embedding"])
        logger.info("[EMBED-BATCH] %d texts — %.0fms", len(texts), (time.perf_counter() - t0) * 1000)
        return results

    async def chat(
        self,
        messages: list[dict],
        system_prompt: str,
        stream: bool = True,
    ) -> AsyncIterator[str]:
        ollama_messages = [{"role": "system", "content": system_prompt}]
        ollama_messages.extend(messages)

        t0 = time.perf_counter()
        logger.info("[CHAT] starting request to %s (stream=%s)", self.chat_model, stream)

        async with httpx.AsyncClient(timeout=120) as client:
            if stream:
                async with client.stream(
                    "POST",
                    f"{self.base_url}/api/chat",
                    json={
                        "model": self.chat_model,
                        "messages": ollama_messages,
                        "stream": True,
                    },
                ) as response:
                    response.raise_for_status()
                    first = True
                    async for line in response.aiter_lines():
                        if not line:
                            continue
                        data = json.loads(line)
                        if content := data.get("message", {}).get("content"):
                            if first:
                                logger.info(
                                    "[CHAT] first token — %.0fms",
                                    (time.perf_counter() - t0) * 1000,
                                )
                                first = False
                            yield content
                        if data.get("done"):
                            break
                logger.info("[CHAT] stream complete — %.0fms", (time.perf_counter() - t0) * 1000)
            else:
                response = await client.post(
                    f"{self.base_url}/api/chat",
                    json={
                        "model": self.chat_model,
                        "messages": ollama_messages,
                        "stream": False,
                    },
                )
                response.raise_for_status()
                logger.info(
                    "[CHAT] non-stream complete — %.0fms", (time.perf_counter() - t0) * 1000
                )
                yield response.json()["message"]["content"]
