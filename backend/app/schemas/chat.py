import uuid
from datetime import datetime

from pydantic import BaseModel


class ChatSessionCreate(BaseModel):
    title: str | None = None
    folder_id: uuid.UUID | None = None


class ChatSessionResponse(BaseModel):
    id: uuid.UUID
    title: str | None
    folder_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ChatSessionDetailResponse(ChatSessionResponse):
    messages: list["ChatMessageResponse"] = []


class ChatMessageCreate(BaseModel):
    content: str
    folder_id: uuid.UUID | None = None


class ChatMessageResponse(BaseModel):
    id: uuid.UUID
    role: str
    content: str
    citations: dict | list | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class EphemeralUploadResponse(BaseModel):
    temp_id: str
    answer: str
    citations: list[dict] | None = None


class EphemeralSaveRequest(BaseModel):
    temp_id: str
    folder_id: uuid.UUID


ChatSessionDetailResponse.model_rebuild()
