import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.config import settings
from app.database import get_db
from app.models import Chunk, Document, DocumentStatus, FileType, Folder, User
from app.schemas import DocumentResponse, DocumentStatusResponse
from app.tasks.indexing import index_document

router = APIRouter(tags=["documents"])

ALLOWED_EXTENSIONS: dict[str, FileType] = {
    ".txt": FileType.TXT,
    ".pdf": FileType.PDF,
    ".md": FileType.MD,
    ".png": FileType.IMAGE,
    ".jpg": FileType.IMAGE,
    ".jpeg": FileType.IMAGE,
    ".webp": FileType.IMAGE,
}


@router.post(
    "/api/folders/{folder_id}/documents",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    folder_id: uuid.UUID,
    file: UploadFile,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Folder).where(Folder.id == folder_id, Folder.user_id == current_user.id)
    )
    folder = result.scalar_one_or_none()
    if not folder:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Folder not found")

    suffix = Path(file.filename).suffix.lower() if file.filename else ""
    file_type = ALLOWED_EXTENSIONS.get(suffix)
    if not file_type:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type: {suffix}. Allowed: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    content = await file.read()
    file_size = len(content)

    doc_id = uuid.uuid4()
    upload_dir = Path(settings.upload_dir) / str(current_user.id) / str(folder_id)
    upload_dir.mkdir(parents=True, exist_ok=True)
    file_path = upload_dir / f"{doc_id}_{file.filename}"
    file_path.write_bytes(content)

    document = Document(
        id=doc_id,
        folder_id=folder_id,
        user_id=current_user.id,
        filename=file.filename or "unknown",
        file_path=str(file_path),
        file_type=file_type,
        file_size_bytes=file_size,
        status=DocumentStatus.PROCESSING,
    )
    db.add(document)
    await db.commit()
    await db.refresh(document)

    index_document.delay(str(document.id))

    return document


@router.get("/api/documents/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Document).where(
            Document.id == document_id, Document.user_id == current_user.id
        )
    )
    document = result.scalar_one_or_none()
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    return document


@router.get("/api/documents/{document_id}/status", response_model=DocumentStatusResponse)
async def get_document_status(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Document).where(
            Document.id == document_id, Document.user_id == current_user.id
        )
    )
    document = result.scalar_one_or_none()
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    return DocumentStatusResponse(
        id=document.id, status=document.status.value, chunk_count=document.chunk_count
    )


@router.get("/api/documents/{document_id}/preview")
async def preview_document(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Document).where(
            Document.id == document_id, Document.user_id == current_user.id
        )
    )
    document = result.scalar_one_or_none()
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    if document.file_type in (FileType.PDF, FileType.IMAGE):
        file_path = Path(document.file_path)
        if not file_path.exists():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found on disk")
        media_types = {
            FileType.PDF: "application/pdf",
            FileType.IMAGE: "image/png",
        }
        return FileResponse(
            file_path,
            media_type=media_types.get(document.file_type, "application/octet-stream"),
            filename=document.filename,
        )

    MAX_PREVIEW_CHARS = 50_000
    truncated = False

    chunks_result = await db.execute(
        select(Chunk.content, Chunk.chunk_index)
        .where(Chunk.document_id == document_id)
        .order_by(Chunk.chunk_index)
        .limit(50)
    )
    chunks = chunks_result.all()

    if chunks:
        parts = []
        total = 0
        for row in chunks:
            if total + len(row.content) > MAX_PREVIEW_CHARS:
                parts.append(row.content[: MAX_PREVIEW_CHARS - total])
                truncated = True
                break
            parts.append(row.content)
            total += len(row.content)
        text = "\n\n".join(parts)
    else:
        file_path = Path(document.file_path)
        if file_path.exists():
            with open(file_path, encoding="utf-8", errors="replace") as f:
                text = f.read(MAX_PREVIEW_CHARS)
                if len(text) == MAX_PREVIEW_CHARS:
                    truncated = True
        else:
            text = ""

    return {
        "id": str(document.id),
        "filename": document.filename,
        "file_type": document.file_type.value,
        "content": text,
        "truncated": truncated,
    }


@router.delete("/api/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Document).where(
            Document.id == document_id, Document.user_id == current_user.id
        )
    )
    document = result.scalar_one_or_none()
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    file_path = Path(document.file_path)
    if file_path.exists():
        file_path.unlink()

    await db.delete(document)
    await db.commit()
