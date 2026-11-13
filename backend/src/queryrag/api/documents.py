import logging
from hashlib import sha256
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from queryrag.config import get_settings
from queryrag.database import get_db
from queryrag.ingestion.service import ingest_pdf
from queryrag.repositories.documents import (
    create_document,
    get_document,
    get_document_by_hash,
    list_documents,
)
from queryrag.schemas import DocumentCreate, DocumentRead, UploadResponse

logger = logging.getLogger("queryrag.documents")

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


@router.post(
    "/upload",
    response_model=UploadResponse,
    status_code=status.HTTP_201_CREATED,
)
def upload_document_endpoint(
    file: UploadFile = File(...),
    database: Session = Depends(get_db),
) -> UploadResponse:
    filename = file.filename or "upload.pdf"
    max_bytes = get_settings().max_upload_mb * 1024 * 1024

    pdf_bytes = file.file.read(max_bytes + 1)

    if not pdf_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The uploaded file is empty",
        )

    if len(pdf_bytes) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"The file is larger than {get_settings().max_upload_mb} MB",
        )

    if not pdf_bytes.startswith(b"%PDF-"):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Only PDF files are supported",
        )

    existing = get_document_by_hash(database, sha256(pdf_bytes).hexdigest())

    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": "This file has already been uploaded",
                "document_id": str(existing.id),
                "status": existing.status,
            },
        )

    try:
        result = ingest_pdf(
            database,
            filename=filename,
            pdf_bytes=pdf_bytes,
        )
    except Exception as error:
        logger.warning("Ingestion failed for %s: %s", filename, error)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="The PDF could not be processed",
        ) from error

    return UploadResponse(
        document_id=result.document_id,
        filename=filename,
        status="indexed",
        page_count=result.page_count,
        chunk_count=result.chunk_count,
    )


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