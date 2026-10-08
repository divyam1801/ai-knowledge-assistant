import logging
import time
import uuid
from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.llm.factory import get_chat_provider
from app.services.llm.prompts import CHAT_SYSTEM_PROMPT
from app.services.search import vector_search

logger = logging.getLogger("app.rag")


def _build_context(chunks: list[dict]) -> str:
    sections: list[str] = []
    for chunk in chunks:
        header = f"[Document: {chunk['document_filename']}, Folder: {chunk['folder_name']}]"
        sections.append(f"{header}\n{chunk['content']}")
    return "\n\n".join(sections)


def _build_citations(chunks: list[dict]) -> list[dict]:
    return [
        {
            "chunk_id": str(chunk["chunk_id"]),
            "document_id": str(chunk["document_id"]),
            "document_filename": chunk["document_filename"],
            "snippet": chunk["content"][:200],
            "similarity": chunk["similarity"],
        }
        for chunk in chunks
    ]


async def rag_query(
    db: AsyncSession,
    question: str,
    user_id: uuid.UUID,
    folder_id: uuid.UUID | None = None,
    chat_history: list[dict] | None = None,
) -> tuple[str, list[dict]]:
    t0 = time.perf_counter()

    chunks = await vector_search(db, question, user_id, folder_id, limit=10)
    t_search = time.perf_counter()
    logger.info("[RAG] vector search — %.0fms, %d chunks", (t_search - t0) * 1000, len(chunks))

    if not chunks:
        return "I couldn't find any relevant information in your knowledge base.", []

    context = _build_context(chunks)
    citations = _build_citations(chunks)

    messages = []
    if chat_history:
        messages.extend(chat_history)
    messages.append({"role": "user", "content": question})

    llm = get_chat_provider()
    system_prompt = CHAT_SYSTEM_PROMPT.format(context=context)
    full_response = ""
    async for token in llm.chat(messages, system_prompt, stream=False):
        full_response += token

    t_llm = time.perf_counter()
    logger.info("[RAG] LLM response — %.0fms, %d chars", (t_llm - t_search) * 1000, len(full_response))
    logger.info("[RAG] total — %.0fms", (t_llm - t0) * 1000)

    return full_response, citations


async def rag_query_stream(
    db: AsyncSession,
    question: str,
    user_id: uuid.UUID,
    folder_id: uuid.UUID | None = None,
    chat_history: list[dict] | None = None,
) -> AsyncIterator[tuple[str, list[dict] | None]]:
    t0 = time.perf_counter()

    chunks = await vector_search(db, question, user_id, folder_id, limit=10)
    t_search = time.perf_counter()
    logger.info("[RAG-stream] vector search — %.0fms, %d chunks", (t_search - t0) * 1000, len(chunks))

    if not chunks:
        yield "I couldn't find any relevant information in your knowledge base.", []
        return

    context = _build_context(chunks)
    citations = _build_citations(chunks)

    messages = []
    if chat_history:
        messages.extend(chat_history)
    messages.append({"role": "user", "content": question})

    llm = get_chat_provider()
    system_prompt = CHAT_SYSTEM_PROMPT.format(context=context)
    token_count = 0
    t_first_token = None
    async for token in llm.chat(messages, system_prompt, stream=True):
        if t_first_token is None:
            t_first_token = time.perf_counter()
            logger.info("[RAG-stream] time to first token — %.0fms", (t_first_token - t_search) * 1000)
        token_count += 1
        yield token, None

    t_done = time.perf_counter()
    logger.info("[RAG-stream] LLM stream done — %.0fms, %d tokens", (t_done - t_search) * 1000, token_count)
    logger.info("[RAG-stream] total — %.0fms", (t_done - t0) * 1000)

    yield "", citations
