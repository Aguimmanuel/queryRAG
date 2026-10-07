from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class DocumentCreate(BaseModel):
    filename: str
    content_type: str
    content_hash: str | None = None


class DocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    filename: str
    content_type: str
    status: str
    content_hash: str | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime

class SearchRequest(BaseModel):
    query: str = Field(min_length=1)
    limit: int = Field(default=5, ge=1, le=20)


class SearchResult(BaseModel):
    document_id: UUID
    page_number: int
    chunk_index: int
    text: str
    distance: float


class SearchResponse(BaseModel):
    query: str
    results: list[SearchResult]