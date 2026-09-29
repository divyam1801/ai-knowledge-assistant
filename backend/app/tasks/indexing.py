import asyncio
import logging
import uuid

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.celery_app import celery_app
from app.config import settings
from app.models import Chunk, Document, DocumentStatus
from app.services.ingestion import process_document_text
from app.services.llm.factory import get_llm_provider

logger = logging.getLogger(__name__)


def _make_session() -> async_sessionmaker[AsyncSession]:
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def index_document(self, document_id: str) -> dict:
    logger.info("[TASK] index_document received for document_id=%s", document_id)
    return asyncio.run(_index_document(self, uuid.UUID(document_id)))


async def _index_document(task, document_id: uuid.UUID) -> dict:
    logger.info("[INDEX] Starting indexing for document %s", document_id)
    session_factory = _make_session()
    async with session_factory() as db:
        result = await db.execute(select(Document).where(Document.id == document_id))
        document = result.scalar_one_or_none()
        if not document:
            logger.error("[INDEX] Document %s not found in DB", document_id)
            return {"status": "error", "detail": "Document not found"}

        logger.info("[INDEX] Found document: %s (type=%s, path=%s)", document.filename, document.file_type, document.file_path)

        try:
            logger.info("[INDEX] Extracting and chunking text...")
            chunks_data = process_document_text(document.file_path, document.file_type)
            logger.info("[INDEX] Extracted %d chunks", len(chunks_data) if chunks_data else 0)

            if not chunks_data:
                await _update_status(db, document_id, DocumentStatus.READY, chunk_count=0)
                return {"status": "ready", "chunks": 0}

            llm = get_llm_provider()
            logger.info("[INDEX] LLM provider: %s — generating embeddings for %d chunks...", type(llm).__name__, len(chunks_data))
            texts = [c["content"] for c in chunks_data]
            embeddings = await llm.embed_batch(texts)
            logger.info("[INDEX] Embeddings generated: %d vectors (dim=%d)", len(embeddings), len(embeddings[0]) if embeddings else 0)

            chunk_models = []
            for chunk_data, embedding in zip(chunks_data, embeddings):
                chunk_models.append(
                    Chunk(
                        document_id=document_id,
                        folder_id=document.folder_id,
                        user_id=document.user_id,
                        content=chunk_data["content"],
                        chunk_index=chunk_data["chunk_index"],
                        token_count=chunk_data["token_count"],
                        embedding=embedding,
                    )
                )

            db.add_all(chunk_models)
            await _update_status(db, document_id, DocumentStatus.READY, chunk_count=len(chunk_models))
            await db.commit()

            logger.info("[INDEX] Successfully indexed document %s: %d chunks stored", document_id, len(chunk_models))
            return {"status": "ready", "chunks": len(chunk_models)}

        except Exception as exc:
            logger.exception("[INDEX] FAILED to index document %s: %s", document_id, exc)
            await db.rollback()
            async with session_factory() as err_db:
                await _update_status(err_db, document_id, DocumentStatus.FAILED)
                await err_db.commit()
            raise task.retry(exc=exc)


async def _update_status(
    db, document_id: uuid.UUID, status: DocumentStatus, chunk_count: int | None = None
) -> None:
    values: dict = {"status": status}
    if chunk_count is not None:
        values["chunk_count"] = chunk_count
    await db.execute(update(Document).where(Document.id == document_id).values(**values))
