import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from queryrag.api import search as search_api
from queryrag.config import get_settings
from queryrag.database import get_db, get_session_factory
from queryrag.ingestion.chunking import TextChunk
from queryrag.main import app
from queryrag.models import Document, DocumentChunk
from queryrag.repositories.chunks import create_document_chunks
from sqlalchemy import delete


@pytest.mark.integration
def test_search_endpoint_returns_ranked_results(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if not os.getenv("DATABASE_URL"):
        pytest.skip("DATABASE_URL is required for the integration test")

    get_settings.cache_clear()

    database = get_session_factory()()
    document = Document(
        filename="search-api-integration.pdf",
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
            text="This passage explains PostgreSQL vector retrieval.",
            metadata={"filename": document.filename},
        )

        second_chunk = TextChunk(
            chunk_id=uuid4().hex,
            page_number=2,
            chunk_index=0,
            text="This passage discusses unrelated cooking instructions.",
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

        monkeypatch.setattr(
            search_api,
            "embed_query",
            lambda query: query_vector,
        )

        def override_get_db():
            yield database

        app.dependency_overrides[get_db] = override_get_db

        client = TestClient(app)
        response = client.post(
            "/search",
            json={
                "query": "Where is vector retrieval explained?",
                "limit": 2,
            },
        )

        assert response.status_code == 200

        payload = response.json()

        assert payload["query"] == "Where is vector retrieval explained?"
        assert len(payload["results"]) == 2
        assert payload["results"][0]["page_number"] == 1
        assert payload["results"][0]["filename"] == document.filename
        assert payload["results"][0]["distance"] < (
            payload["results"][1]["distance"]
        )

    finally:
        app.dependency_overrides.clear()

        database.execute(
            delete(DocumentChunk).where(
                DocumentChunk.document_id == document.id
            )
        )

        database.delete(document)
        database.commit()
        database.close()
