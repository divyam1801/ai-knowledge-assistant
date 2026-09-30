import logging
import time
import uuid

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Chunk, Document, Folder
from app.services.llm.factory import get_llm_provider

logger = logging.getLogger("app.search")


async def vector_search(
    db: AsyncSession,
    query: str,
    user_id: uuid.UUID,
    folder_id: uuid.UUID | None = None,
    limit: int = 10,
) -> list[dict]:
    t0 = time.perf_counter()
    llm = get_llm_provider()
    query_embedding = await llm.embed(query)
    t_embed = time.perf_counter()
    logger.info("[SEARCH] query embedding — %.0fms", (t_embed - t0) * 1000)

    embedding_str = "[" + ",".join(str(v) for v in query_embedding) + "]"

    stmt = (
        select(
            Chunk.id,
            Chunk.content,
            Chunk.chunk_index,
            Chunk.metadata_.label("metadata"),
            Chunk.document_id,
            Document.filename.label("document_filename"),
            Folder.name.label("folder_name"),
            (1 - Chunk.embedding.cosine_distance(text(f"'{embedding_str}'::vector"))).label(
                "similarity"
            ),
        )
        .join(Document, Document.id == Chunk.document_id)
        .join(Folder, Folder.id == Chunk.folder_id)
        .where(Chunk.user_id == user_id)
    )

    if folder_id:
        stmt = stmt.where(Chunk.folder_id == folder_id)

    stmt = stmt.order_by(
        Chunk.embedding.cosine_distance(text(f"'{embedding_str}'::vector"))
    ).limit(limit)

    result = await db.execute(stmt)
    t_query = time.perf_counter()
    rows = result.all()
    logger.info("[SEARCH] pgvector query — %.0fms, %d results", (t_query - t_embed) * 1000, len(rows))
    logger.info("[SEARCH] total — %.0fms", (t_query - t0) * 1000)

    return [
        {
            "chunk_id": row.id,
            "document_id": row.document_id,
            "document_filename": row.document_filename,
            "folder_name": row.folder_name,
            "content": row.content,
            "similarity": float(row.similarity),
            "chunk_index": row.chunk_index,
            "metadata": row.metadata,
        }
        for row in rows
    ]
