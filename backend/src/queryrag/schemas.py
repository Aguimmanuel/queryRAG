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
    status: str = Field(description="uploaded, indexed or failed")
    content_hash: str | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime

class UploadResponse(BaseModel):
    document_id: UUID
    filename: str
    status: str
    page_count: int
    chunk_count: int

class SearchRequest(BaseModel):
    query: str = Field(min_length=1)
    limit: int = Field(default=5, ge=1, le=20)


class SearchResult(BaseModel):
    document_id: UUID
    filename: str
    page_number: int
    chunk_index: int
    text: str
    distance: float = Field(description="Cosine distance to the query; lower is closer")


class SearchResponse(BaseModel):
    query: str
    results: list[SearchResult]

class AnswerRequest(BaseModel):
    query: str = Field(min_length=1)
    limit: int = Field(default=5, ge=1, le=20)


class Citation(BaseModel):
    document_id: UUID
    filename: str
    page_number: int
    chunk_index: int
    distance: float = Field(description="Cosine distance to the query; lower is closer")
    text: str


class AnswerResponse(BaseModel):
    query: str
    answer: str
    citations: list[Citation] = Field(
        description="Evidence chunks given to the model (empty when abstaining)"
    )
    grounded: bool
    insufficient_evidence: bool = Field(
        description="True when the API declined to answer for lack of evidence"
    )


# --- Operational responses (/health, /ready) ---


class HealthResponse(BaseModel):
    status: str
    service: str


class ReadinessResponse(BaseModel):
    status: str = Field(description="ready or not_ready")
    database: str = Field(description="ok, missing_configuration or unavailable")


# --- Error responses (documented in the OpenAPI contract) ---


class ErrorResponse(BaseModel):
    detail: str


class DuplicateDocumentDetail(BaseModel):
    message: str
    document_id: UUID
    status: str


class DuplicateDocumentResponse(BaseModel):
    detail: DuplicateDocumentDetail
