import json
from collections.abc import AsyncIterator

import httpx

from app.services.llm.base import LLMProvider

EMBED_BATCH_SIZE = 32


class OllamaProvider(LLMProvider):
    def __init__(self, base_url: str, embed_model: str, chat_model: str):
        self.base_url = base_url.rstrip("/")
        self.embed_model = embed_model
        self.chat_model = chat_model

    async def embed(self, text: str) -> list[float]:
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                f"{self.base_url}/api/embeddings",
                json={"model": self.embed_model, "prompt": text},
            )
            response.raise_for_status()
            return response.json()["embedding"]

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
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
        return results

    async def chat(
        self,
        messages: list[dict],
        context: str,
        stream: bool = True,
    ) -> AsyncIterator[str]:
        system_prompt = (
            "You are a knowledgeable study assistant. Answer the user's question "
            "using ONLY the provided context. Structure your response clearly:\n"
            "- Use headings, bullet points, and numbered lists where appropriate\n"
            "- Explain concepts thoroughly in your own words, don't just copy text\n"
            "- Include relevant examples or code snippets from the context\n"
            "- Mention which document the information comes from naturally in your answer\n"
            "- If the context doesn't fully answer the question, say what's missing\n\n"
            f"CONTEXT:\n{context}"
        )

        ollama_messages = [{"role": "system", "content": system_prompt}]
        ollama_messages.extend(messages)

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
                    async for line in response.aiter_lines():
                        if not line:
                            continue
                        data = json.loads(line)
                        if content := data.get("message", {}).get("content"):
                            yield content
                        if data.get("done"):
                            break
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
                yield response.json()["message"]["content"]

    async def summarize(self, text: str) -> str:
        messages = [
            {
                "role": "user",
                "content": (
                    "Summarize the following text concisely, preserving key facts and concepts:\n\n"
                    f"{text}"
                ),
            }
        ]
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(
                f"{self.base_url}/api/chat",
                json={
                    "model": self.chat_model,
                    "messages": messages,
                    "stream": False,
                },
            )
            response.raise_for_status()
            return response.json()["message"]["content"]
