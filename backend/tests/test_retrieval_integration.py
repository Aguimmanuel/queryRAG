import os
from uuid import uuid4

import pytest
from sqlalchemy import delete

from queryrag.config import get_settings
from queryrag.database import get_session_factory
from queryrag.ingestion.chunking import TextChunk
from queryrag.models import Document, DocumentChunk
from queryrag.repositories.chunks import (
    create_document_chunks,
    search_document_chunks,
)


@pytest.mark.integration
def test_vector_search_returns_most_similar_chunk_first() -> None:
    if not os.getenv("DATABASE_URL"):
        pytest.skip("DATABASE_URL is required for the integration test")

    get_settings.cache_clear()

    database = get_session_factory()()
    document = Document(
        filename="retrieval-integration.pdf",
        content_type="application/pdf",
        content_hash=uuid4().hex,
    )

    try:
        database.add(document)
        database.commit()
        database.refresh(document)

        first_chunk = TextChunk(
            chunk_id=uuid4().hex,
            page_number=1,
            chunk_index=0,
            text="The document discusses PostgreSQL vector retrieval.",
            metadata={"filename": document.filename},
        )

        second_chunk = TextChunk(
            chunk_id=uuid4().hex,
            page_number=2,
            chunk_index=0,
            text="The document discusses unrelated cooking instructions.",
            metadata={"filename": document.filename},
        )

        first_vector = [1.0] + [0.0] * 383
        second_vector = [0.0, 1.0] + [0.0] * 382
        query_vector = [1.0] + [0.0] * 383

        create_document_chunks(
            database,
            document.id,
            [first_chunk, second_chunk],
            [first_vector, second_vector],
        )

        results = search_document_chunks(
            database,
            query_vector,
            limit=2,
        )

        assert len(results) == 2
        assert results[0][0].chunk_id == first_chunk.chunk_id
        assert results[0][1] < results[1][1]

    finally:
        database.execute(
            delete(DocumentChunk).where(
                DocumentChunk.document_id == document.id
            )
        )

        database.delete(document)
        database.commit()
        database.close()
