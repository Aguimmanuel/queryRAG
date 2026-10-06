from uuid import UUID

from sqlalchemy.orm import Session

from queryrag.ingestion.chunking import TextChunk
from queryrag.models import DocumentChunk
from sqlalchemy import select


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

def search_document_chunks(
    database: Session,
    query_embedding: list[float],
    *,
    limit: int = 5,
) -> list[tuple[DocumentChunk, float]]:
    if limit <= 0:
        raise ValueError("limit must be greater than zero")

    distance = DocumentChunk.embedding.cosine_distance(query_embedding).label(
        "distance"
    )

    statement = select(DocumentChunk, distance).order_by(distance).limit(limit)

    rows = database.execute(statement).all()

    return [(chunk, float(distance_value)) for chunk, distance_value in rows]