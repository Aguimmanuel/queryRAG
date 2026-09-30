from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from queryrag.database import get_db
from queryrag.repositories.documents import (
    create_document,
    get_document,
    list_documents,
)
from queryrag.schemas import DocumentCreate, DocumentRead


router = APIRouter(
    prefix="/documents",
    tags=["documents"],
)


@router.post(
    "",
    response_model=DocumentRead,
    status_code=status.HTTP_201_CREATED,
)
def create_document_endpoint(
    payload: DocumentCreate,
    database: Session = Depends(get_db),
) -> DocumentRead:
    return create_document(database, payload)


@router.get(
    "",
    response_model=list[DocumentRead],
)
def list_documents_endpoint(
    database: Session = Depends(get_db),
) -> list[DocumentRead]:
    return list_documents(database)


@router.get(
    "/{document_id}",
    response_model=DocumentRead,
)
def get_document_endpoint(
    document_id: UUID,
    database: Session = Depends(get_db),
) -> DocumentRead:
    document = get_document(database, document_id)

    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    return document
