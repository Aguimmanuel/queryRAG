"""DELETE /documents/{id} against the real database.

Deleting a document must also delete its chunks (ON DELETE CASCADE) and free
its fingerprint, so the same PDF can be uploaded again.
"""

import os
from hashlib import sha256
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from queryrag.config import get_settings
from queryrag.database import get_session_factory
from queryrag.ingestion import service as ingestion_service
from queryrag.ingestion.parser import ParsedPage
from queryrag.main import app
from queryrag.models import Document, DocumentChunk
from sqlalchemy import delete, func, select

pytestmark = pytest.mark.integration


@pytest.fixture
def pdf_bytes(monkeypatch):
    if not os.getenv("DATABASE_URL"):
        pytest.skip("DATABASE_URL is required for the integration test")

    get_settings.cache_clear()

    # Skip real PDF parsing and embedding; keep the real database work.
    pages = [
        ParsedPage(page_number=1, text="First page text.", metadata={}),
        ParsedPage(page_number=2, text="Second page text.", metadata={}),
    ]
    monkeypatch.setattr(ingestion_service, "parse_pdf_bytes", lambda b, n: pages)
    monkeypatch.setattr(
        ingestion_service, "embed_texts", lambda texts: [[0.1] * 384 for _ in texts]
    )

    content = f"%PDF-delete-{uuid4().hex}".encode()

    yield content

    cleanup = get_session_factory()()
    cleanup.execute(
        delete(Document).where(Document.content_hash == sha256(content).hexdigest())
    )
    cleanup.commit()
    cleanup.close()


def ingest(pdf_bytes: bytes):
    session = get_session_factory()()

    try:
        return ingestion_service.ingest_pdf(
            session, filename="to-delete.pdf", pdf_bytes=pdf_bytes
        )

    finally:
        session.close()


def count(model, document_id) -> int:
    """Count rows from a NEW session, like another request would."""
    fresh = get_session_factory()()
    column = model.id if model is Document else model.document_id

    try:
        return fresh.scalar(
            select(func.count()).select_from(model).where(column == document_id)
        )

    finally:
        fresh.close()


def test_delete_removes_document_and_its_chunks(pdf_bytes) -> None:
    result = ingest(pdf_bytes)
    assert count(Document, result.document_id) == 1
    assert count(DocumentChunk, result.document_id) == result.chunk_count > 0

    response = TestClient(app).delete(f"/documents/{result.document_id}")

    assert response.status_code == 204
    assert count(Document, result.document_id) == 0
    assert count(DocumentChunk, result.document_id) == 0  # cascade worked


def test_same_pdf_can_be_uploaded_again_after_delete(pdf_bytes) -> None:
    first = ingest(pdf_bytes)
    TestClient(app).delete(f"/documents/{first.document_id}")

    second = ingest(pdf_bytes)  # no DuplicateDocumentError: the hash was freed

    assert second.document_id != first.document_id
    assert count(Document, second.document_id) == 1


def test_delete_twice_returns_404_the_second_time(pdf_bytes) -> None:
    result = ingest(pdf_bytes)
    client = TestClient(app)

    assert client.delete(f"/documents/{result.document_id}").status_code == 204
    assert client.delete(f"/documents/{result.document_id}").status_code == 404
