import uuid
from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.llm.factory import get_llm_provider
from app.services.search import vector_search


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
    chunks = await vector_search(db, question, user_id, folder_id, limit=10)

    if not chunks:
        return "I couldn't find any relevant information in your knowledge base.", []

    context = _build_context(chunks)
    citations = _build_citations(chunks)

    messages = []
    if chat_history:
        messages.extend(chat_history)
    messages.append({"role": "user", "content": question})

    llm = get_llm_provider()
    full_response = ""
    async for token in llm.chat(messages, context, stream=False):
        full_response += token

    return full_response, citations


async def rag_query_stream(
    db: AsyncSession,
    question: str,
    user_id: uuid.UUID,
    folder_id: uuid.UUID | None = None,
    chat_history: list[dict] | None = None,
) -> AsyncIterator[tuple[str, list[dict] | None]]:
    chunks = await vector_search(db, question, user_id, folder_id, limit=10)

    if not chunks:
        yield "I couldn't find any relevant information in your knowledge base.", []
        return

    context = _build_context(chunks)
    citations = _build_citations(chunks)

    messages = []
    if chat_history:
        messages.extend(chat_history)
    messages.append({"role": "user", "content": question})

    llm = get_llm_provider()
    async for token in llm.chat(messages, context, stream=True):
        yield token, None

    yield "", citations
