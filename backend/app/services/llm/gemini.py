import logging
import time
from collections.abc import AsyncIterator

from google import genai
from google.genai import types

from app.services.llm.base import LLMProvider

logger = logging.getLogger("app.gemini")
EMBED_BATCH_SIZE = 100


class GeminiProvider(LLMProvider):
    def __init__(self, api_key: str, embed_model: str, chat_model: str):
        self.client = genai.Client(api_key=api_key)
        self.embed_model = embed_model
        self.chat_model = chat_model
        logger.info("[INIT] Gemini provider initialized (embed=%s, chat=%s)", embed_model, chat_model)

    async def embed(self, text: str) -> list[float]:
        logger.info("[EMBED] Calling Gemini Embedding API (model=%s)", self.embed_model)
        logger.info("[EMBED] Generating embedding for text (%d chars)...", len(text))
        t0 = time.perf_counter()
        result = self.client.models.embed_content(
            model=self.embed_model,
            contents=text,
            config=types.EmbedContentConfig(output_dimensionality=768),
        )
        elapsed = (time.perf_counter() - t0) * 1000
        dims = len(result.embeddings[0].values)
        logger.info("[EMBED] Embedding generated — %d dimensions, %.0fms", dims, elapsed)
        return list(result.embeddings[0].values)

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        logger.info("[EMBED-BATCH] Calling Gemini Embedding API (model=%s)", self.embed_model)
        logger.info("[EMBED-BATCH] Generating embeddings for %d texts...", len(texts))
        t0 = time.perf_counter()
        results: list[list[float]] = []
        for i in range(0, len(texts), EMBED_BATCH_SIZE):
            batch = texts[i : i + EMBED_BATCH_SIZE]
            logger.info("[EMBED-BATCH] Processing batch %d-%d of %d...", i + 1, i + len(batch), len(texts))
            result = self.client.models.embed_content(
                model=self.embed_model,
                contents=batch,
                config=types.EmbedContentConfig(output_dimensionality=768),
            )
            results.extend(list(e.values) for e in result.embeddings)
        elapsed = (time.perf_counter() - t0) * 1000
        logger.info("[EMBED-BATCH] All embeddings generated — %d vectors, %.0fms", len(results), elapsed)
        return results

    async def chat(
        self,
        messages: list[dict],
        system_prompt: str,
        stream: bool = True,
    ) -> AsyncIterator[str]:
        gemini_contents = []
        for msg in messages:
            role = "model" if msg["role"] == "assistant" else "user"
            gemini_contents.append(
                types.Content(role=role, parts=[types.Part(text=msg["content"])])
            )

        logger.info("[CHAT] Calling Gemini Chat API (model=%s, stream=%s)", self.chat_model, stream)
        logger.info("[CHAT] Generating response for %d messages...", len(messages))
        t0 = time.perf_counter()

        config = types.GenerateContentConfig(system_instruction=system_prompt)

        if stream:
            logger.info("[CHAT] Streaming response...")
            first = True
            for chunk in self.client.models.generate_content_stream(
                model=self.chat_model,
                contents=gemini_contents,
                config=config,
            ):
                if chunk.text:
                    if first:
                        logger.info(
                            "[CHAT] First token received — %.0fms", (time.perf_counter() - t0) * 1000
                        )
                        first = False
                    yield chunk.text
            logger.info("[CHAT] Response stream complete — %.0fms", (time.perf_counter() - t0) * 1000)
        else:
            response = self.client.models.generate_content(
                model=self.chat_model,
                contents=gemini_contents,
                config=config,
            )
            elapsed = (time.perf_counter() - t0) * 1000
            logger.info("[CHAT] Response generated — %d chars, %.0fms", len(response.text), elapsed)
            yield response.text
