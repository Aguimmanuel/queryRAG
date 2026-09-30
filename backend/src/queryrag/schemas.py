from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


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
