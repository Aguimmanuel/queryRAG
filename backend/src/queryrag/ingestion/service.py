from dataclasses import dataclass
from hashlib import sha256
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from queryrag.embeddings import embed_texts
from queryrag.ingestion.chunking import chunk_pages
from queryrag.ingestion.parser import parse_pdf_bytes
from queryrag.repositories.chunks import create_document_chunks
from queryrag.repositories.documents import create_document, get_document_by_hash
from queryrag.schemas import DocumentCreate

MAX_ERROR_MESSAGE_LENGTH = 500


class DuplicateDocumentError(Exception):
    """The same file (same SHA-256 hash) is already stored.

    Raised when the UNIQUE constraint on documents.content_hash rejects the
    INSERT, e.g. when two uploads of one file arrive at the same moment.
    """

    def __init__(self, document_id: UUID, status: str) -> None:
        super().__init__(f"Document {document_id} already has this content")
        self.document_id = document_id
        self.status = status


@dataclass(frozen=True)
class IngestionResult:
    document_id: UUID
    page_count: int
    chunk_count: int


def ingest_pdf(
    database: Session,
    *,
    filename: str,
    pdf_bytes: bytes,
    content_type: str = "application/pdf",
) -> IngestionResult:
    """Ingest one PDF. This service owns the transactions.

    Transaction 1: save the document row, so a later failure can be recorded.
    Transaction 2: save all chunks AND mark the document indexed, together.
    On failure: roll back transaction 2, then record status "failed".
    """
    content_hash = sha256(pdf_bytes).hexdigest()

    try:
        document = create_document(
            database,
            DocumentCreate(
                filename=filename,
                content_type=content_type,
                content_hash=content_hash,
            ),
        )
        database.commit()  # transaction 1 is finished here, in the service

    except IntegrityError:
        # The UNIQUE constraint said no. Reset the session, then find the winner.
        database.rollback()
        existing = get_document_by_hash(database, content_hash)

        if existing is None:
            raise  # some other constraint failed: not a duplicate

        raise DuplicateDocumentError(existing.id, existing.status) from None

    try:
        pages = parse_pdf_bytes(
            pdf_bytes,
            filename,
        )

        chunks = chunk_pages(pages)
        embeddings = embed_texts([chunk.text for chunk in chunks])

        create_document_chunks(
            database,
            document.id,
            chunks,
            embeddings,
        )

        document.status = "indexed"
        database.commit()  # transaction 2: chunks + status, all or nothing
        database.refresh(document)

        return IngestionResult(
            document_id=document.id,
            page_count=len(pages),
            chunk_count=len(chunks),
        )

    except Exception as error:
        database.rollback()  # undo half-saved chunks, reset the session
        document.status = "failed"
        document.error_message = str(error)[:MAX_ERROR_MESSAGE_LENGTH]
        database.commit()
        raise