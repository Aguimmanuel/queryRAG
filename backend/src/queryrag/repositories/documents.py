from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from queryrag.models import Document
from queryrag.schemas import DocumentCreate


def create_document(
    database: Session,
    payload: DocumentCreate,
) -> Document:
    document = Document(
        filename=payload.filename,
        content_type=payload.content_type,
        content_hash=payload.content_hash,
    )

    database.add(document)
    database.commit()
    database.refresh(document)

    return document


def list_documents(database: Session) -> list[Document]:
    statement = select(Document).order_by(Document.created_at.desc())

    return list(database.scalars(statement).all())


def get_document(
    database: Session,
    document_id: UUID,
) -> Document | None:
    return database.get(Document, document_id)
