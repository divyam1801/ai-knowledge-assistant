import uuid
from datetime import datetime

from pydantic import BaseModel


class FolderCreate(BaseModel):
    name: str
    description: str | None = None


class FolderUpdate(BaseModel):
    name: str | None = None
    description: str | None = None


class FolderResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    document_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class FolderDetailResponse(FolderResponse):
    documents: list["DocumentSummary"] = []


class DocumentSummary(BaseModel):
    id: uuid.UUID
    filename: str
    file_type: str
    status: str
    uploaded_at: datetime

    model_config = {"from_attributes": True}


FolderDetailResponse.model_rebuild()
