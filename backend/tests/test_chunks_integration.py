import os
from uuid import uuid4

import pytest
from sqlalchemy import delete, select

from queryrag.config import get_settings
from queryrag.database import get_session_factory
from queryrag.ingestion.chunking import TextChunk
from queryrag.models import Document, DocumentChunk
from queryrag.repositories.chunks import create_document_chunks


@pytest.mark.integration
def test_store_document_chunks_with_embeddings() -> None:
    if not os.getenv("DATABASE_URL"):
        pytest.skip("DATABASE_URL is required for the integration test")

    get_settings.cache_clear()

    database = get_session_factory()()
    document = Document(
        filename="integration-sample.pdf",
        content_type="application/pdf",
        content_hash=uuid4().hex,
    )

    try:
        database.add(document)
        database.commit()
        database.refresh(document)

        chunks = [
            TextChunk(
                chunk_id=uuid4().hex,
                page_number=1,
                chunk_index=0,
                text="The first test passage.",
                metadata={"filename": "integration-sample.pdf"},
            ),
            TextChunk(
                chunk_id=uuid4().hex,
                page_number=2,
                chunk_index=0,
                text="The second test passage.",
                metadata={"filename": "integration-sample.pdf"},
            ),
        ]

        embeddings = [
            [0.1] * 384,
            [0.2] * 384,
        ]

        stored_chunks = create_document_chunks(
            database,
            document.id,
            chunks,
            embeddings,
        )

        assert len(stored_chunks) == 2

        statement = select(DocumentChunk).where(
            DocumentChunk.document_id == document.id
        )
        database_chunks = list(database.scalars(statement).all())

        assert len(database_chunks) == 2
        assert all(len(chunk.embedding) == 384 for chunk in database_chunks)
        assert {
            chunk.page_number for chunk in database_chunks
        } == {1, 2}

    finally:
        database.execute(
            delete(DocumentChunk).where(
                DocumentChunk.document_id == document.id
            )
        )

        if document.id is not None:
            database.delete(document)

        database.commit()
        database.close()
