import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.database import get_db
from app.models import Document, Folder, User
from app.services.summarization import summarize_by_date, summarize_document, summarize_folder

router = APIRouter(prefix="/api/summarize", tags=["summarize"])


class SummaryResponse(BaseModel):
    summary: str


@router.get("/folder/{folder_id}", response_model=SummaryResponse)
async def get_folder_summary(
    folder_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Folder).where(Folder.id == folder_id, Folder.user_id == current_user.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Folder not found")

    summary = await summarize_folder(db, folder_id, current_user.id)
    return SummaryResponse(summary=summary)


@router.get("/document/{document_id}", response_model=SummaryResponse)
async def get_document_summary(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Document).where(Document.id == document_id, Document.user_id == current_user.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    summary = await summarize_document(db, document_id, current_user.id)
    return SummaryResponse(summary=summary)


@router.get("/date/{target_date}", response_model=SummaryResponse)
async def get_date_summary(
    target_date: date,
    folder_id: uuid.UUID | None = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    summary = await summarize_by_date(db, current_user.id, target_date, folder_id)
    return SummaryResponse(summary=summary)
