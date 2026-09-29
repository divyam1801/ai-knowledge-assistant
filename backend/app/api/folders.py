import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user
from app.database import get_db
from app.models import Document, Folder, User
from app.schemas import FolderCreate, FolderDetailResponse, FolderResponse, FolderUpdate

router = APIRouter(prefix="/api/folders", tags=["folders"])


@router.post("", response_model=FolderResponse, status_code=status.HTTP_201_CREATED)
async def create_folder(
    data: FolderCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    folder = Folder(user_id=current_user.id, name=data.name, description=data.description)
    db.add(folder)
    await db.commit()
    await db.refresh(folder)
    return folder


@router.get("", response_model=list[FolderResponse])
async def list_folders(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(
            Folder,
            func.count(Document.id).label("document_count"),
        )
        .outerjoin(Document, Document.folder_id == Folder.id)
        .where(Folder.user_id == current_user.id)
        .group_by(Folder.id)
        .order_by(Folder.created_at.desc())
    )
    folders = []
    for folder, doc_count in result.all():
        response = FolderResponse.model_validate(folder)
        response.document_count = doc_count
        folders.append(response)
    return folders


@router.get("/{folder_id}", response_model=FolderDetailResponse)
async def get_folder(
    folder_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Folder)
        .options(selectinload(Folder.documents))
        .where(Folder.id == folder_id, Folder.user_id == current_user.id)
    )
    folder = result.scalar_one_or_none()
    if not folder:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Folder not found")
    return folder


@router.patch("/{folder_id}", response_model=FolderResponse)
async def update_folder(
    folder_id: uuid.UUID,
    data: FolderUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Folder).where(Folder.id == folder_id, Folder.user_id == current_user.id)
    )
    folder = result.scalar_one_or_none()
    if not folder:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Folder not found")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(folder, field, value)

    await db.commit()
    await db.refresh(folder)
    return folder


@router.delete("/{folder_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_folder(
    folder_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Folder).where(Folder.id == folder_id, Folder.user_id == current_user.id)
    )
    folder = result.scalar_one_or_none()
    if not folder:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Folder not found")

    await db.delete(folder)
    await db.commit()
