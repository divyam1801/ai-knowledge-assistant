import io
import uuid
from pathlib import Path

import numpy as np

from app.models import FileType
from app.services.ingestion import extract_text, process_document_text
from app.services.llm.factory import get_chat_provider, get_embed_provider
from app.services.llm.prompts import CHAT_SYSTEM_PROMPT

_ephemeral_store: dict[str, dict] = {}


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    a_arr = np.array(a)
    b_arr = np.array(b)
    return float(np.dot(a_arr, b_arr) / (np.linalg.norm(a_arr) * np.linalg.norm(b_arr) + 1e-10))


async def process_ephemeral_upload(
    file_content: bytes,
    filename: str,
    question: str,
    user_id: uuid.UUID,
) -> dict:
    suffix = Path(filename).suffix.lower()
    ext_to_type = {
        ".txt": FileType.TXT,
        ".md": FileType.MD,
        ".pdf": FileType.PDF,
        ".png": FileType.IMAGE,
        ".jpg": FileType.IMAGE,
        ".jpeg": FileType.IMAGE,
        ".webp": FileType.IMAGE,
    }
    file_type = ext_to_type.get(suffix)
    if not file_type:
        raise ValueError(f"Unsupported file type: {suffix}")

    import tempfile

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(file_content)
        tmp_path = tmp.name

    try:
        chunks = process_document_text(tmp_path, file_type)
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    if not chunks:
        return {
            "temp_id": "",
            "answer": "Could not extract any text from the uploaded file.",
            "citations": None,
        }

    embed_llm = get_embed_provider()
    chunk_texts = [c["content"] for c in chunks]
    embeddings = await embed_llm.embed_batch(chunk_texts)
    query_embedding = await embed_llm.embed(question)

    scored = []
    for i, emb in enumerate(embeddings):
        sim = _cosine_similarity(query_embedding, emb)
        scored.append((sim, i))
    scored.sort(reverse=True)
    top_k = scored[:10]

    context_parts = []
    citations = []
    for sim, idx in top_k:
        content = chunk_texts[idx]
        context_parts.append(f"[Document: {filename}]\n{content}")
        citations.append({
            "chunk_id": str(idx),
            "document_id": "ephemeral",
            "document_filename": filename,
            "snippet": content[:200],
            "similarity": sim,
        })

    context = "\n\n".join(context_parts)
    messages = [{"role": "user", "content": question}]

    chat_llm = get_chat_provider()
    system_prompt = CHAT_SYSTEM_PROMPT.format(context=context)
    full_response = ""
    async for token in chat_llm.chat(messages, system_prompt, stream=False):
        full_response += token

    temp_id = str(uuid.uuid4())
    _ephemeral_store[temp_id] = {
        "user_id": user_id,
        "file_content": file_content,
        "filename": filename,
        "file_type": file_type,
    }

    return {
        "temp_id": temp_id,
        "answer": full_response,
        "citations": citations,
    }


def get_ephemeral_data(temp_id: str, user_id: uuid.UUID) -> dict | None:
    data = _ephemeral_store.get(temp_id)
    if data and data["user_id"] == user_id:
        return data
    return None


def remove_ephemeral(temp_id: str) -> None:
    _ephemeral_store.pop(temp_id, None)
