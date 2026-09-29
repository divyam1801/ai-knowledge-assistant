import uuid

from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    query: str
    folder_id: uuid.UUID | None = None
    limit: int = Field(default=10, ge=1, le=50)


class SearchChunkResult(BaseModel):
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    document_filename: str
    folder_name: str
    content: str
    similarity: float
    chunk_index: int
    metadata: dict | None = None


class SearchResponse(BaseModel):
    query: str
    results: list[SearchChunkResult]
    total: int
