from uuid import UUID

from sqlalchemy.orm import Session

from queryrag.ingestion.chunking import TextChunk
from queryrag.models import DocumentChunk


def create_document_chunks(
    database: Session,
    document_id: UUID,
    chunks: list[TextChunk],
    embeddings: list[list[float]],
) -> list[DocumentChunk]:
    if len(chunks) != len(embeddings):
        raise ValueError(
            "The number of chunks must match the number of embeddings"
        )

    records = [
        DocumentChunk(
            document_id=document_id,
            chunk_id=chunk.chunk_id,
            page_number=chunk.page_number,
            chunk_index=chunk.chunk_index,
            text=chunk.text,
            embedding=embedding,
        )
        for chunk, embedding in zip(
            chunks,
            embeddings,
            strict=True,
        )
    ]

    database.add_all(records)
    database.commit()

    for record in records:
        database.refresh(record)

    return records
