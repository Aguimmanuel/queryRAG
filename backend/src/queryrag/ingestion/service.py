from dataclasses import dataclass
from hashlib import sha256
from uuid import UUID

from sqlalchemy.orm import Session

from queryrag.embeddings import embed_texts
from queryrag.ingestion.chunking import chunk_pages
from queryrag.ingestion.parser import parse_pdf_bytes
from queryrag.repositories.chunks import create_document_chunks
from queryrag.repositories.documents import create_document
from queryrag.schemas import DocumentCreate


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
    content_hash = sha256(pdf_bytes).hexdigest()

    document = create_document(
        database,
        DocumentCreate(
            filename=filename,
            content_type=content_type,
            content_hash=content_hash,
        ),
    )

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
        database.commit()
        database.refresh(document)

        return IngestionResult(
            document_id=document.id,
            page_count=len(pages),
            chunk_count=len(chunks),
        )

    except Exception as error:
        document.status = "failed"
        document.error_message = str(error)
        database.commit()
        raise
