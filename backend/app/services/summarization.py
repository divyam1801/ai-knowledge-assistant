import uuid
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Chunk, Document, Folder
from app.services.llm.factory import get_chat_provider
from app.services.llm.prompts import SUMMARIZE_PROMPT


async def summarize_folder(db: AsyncSession, folder_id: uuid.UUID, user_id: uuid.UUID) -> str:
    result = await db.execute(
        select(Chunk.content)
        .join(Document, Document.id == Chunk.document_id)
        .where(Chunk.folder_id == folder_id, Chunk.user_id == user_id)
        .order_by(Chunk.chunk_index)
        .limit(50)
    )
    contents = [row[0] for row in result.all()]
    if not contents:
        return "No content found in this folder."

    combined = "\n\n".join(contents)
    return await _summarize(combined)


async def summarize_document(db: AsyncSession, document_id: uuid.UUID, user_id: uuid.UUID) -> str:
    result = await db.execute(
        select(Chunk.content)
        .where(Chunk.document_id == document_id, Chunk.user_id == user_id)
        .order_by(Chunk.chunk_index)
    )
    contents = [row[0] for row in result.all()]
    if not contents:
        return "No content found in this document."

    combined = "\n\n".join(contents)
    return await _summarize(combined)


async def summarize_by_date(
    db: AsyncSession, user_id: uuid.UUID, target_date: date, folder_id: uuid.UUID | None = None,
) -> str:
    stmt = (
        select(Chunk.content, Document.filename)
        .join(Document, Document.id == Chunk.document_id)
        .where(
            Chunk.user_id == user_id,
            Document.created_at >= target_date,
            Document.created_at < target_date + timedelta(days=1),
        )
        .order_by(Document.filename, Chunk.chunk_index)
        .limit(50)
    )
    if folder_id:
        stmt = stmt.where(Chunk.folder_id == folder_id)

    result = await db.execute(stmt)
    rows = result.all()
    if not rows:
        return f"No content found for {target_date.isoformat()}."

    combined = "\n\n".join(f"[{row.filename}]\n{row.content}" for row in rows)
    return await _summarize(combined)


async def _summarize(text: str) -> str:
    llm = get_chat_provider()
    prompt = SUMMARIZE_PROMPT.format(text=text)
    result = ""
    async for token in llm.chat([{"role": "user", "content": prompt}], system_prompt="", stream=False):
        result += token
    return result
