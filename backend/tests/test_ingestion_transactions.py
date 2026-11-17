import os
from uuid import uuid4

import pytest
from queryrag.config import get_settings
from queryrag.database import get_session_factory
from queryrag.ingestion import service as ingestion_service
from queryrag.ingestion.parser import ParsedPage
from queryrag.models import Document, DocumentChunk
from sqlalchemy import delete, func, select

pytestmark = pytest.mark.integration


@pytest.fixture
def database():
    if not os.getenv("DATABASE_URL"):
        pytest.skip("DATABASE_URL is required for the integration test")

    get_settings.cache_clear()
    session = get_session_factory()()

    yield session

    session.close()


@pytest.fixture
def fake_pdf(monkeypatch):
    """Skip real PDF parsing and embedding; keep the real database work."""
    filename = f"transaction-test-{uuid4().hex}.pdf"
    pdf_bytes = f"%PDF-fake-{uuid4().hex}".encode()

    pages = [
        ParsedPage(page_number=1, text="First page text.", metadata={}),
        ParsedPage(page_number=2, text="Second page text.", metadata={}),
    ]
    monkeypatch.setattr(
        ingestion_service,
        "parse_pdf_bytes",
        lambda content, name: pages,
    )

    yield filename, pdf_bytes

    cleanup = get_session_factory()()
    ids = select(Document.id).where(Document.filename == filename)
    cleanup.execute(delete(DocumentChunk).where(DocumentChunk.document_id.in_(ids)))
    cleanup.execute(delete(Document).where(Document.filename == filename))
    cleanup.commit()
    cleanup.close()


def read_state(filename: str) -> tuple[str | None, int]:
    """Look at the database from a NEW session, like another request would."""
    fresh = get_session_factory()()

    try:
        document = fresh.scalars(
            select(Document).where(Document.filename == filename)
        ).first()

        if document is None:
            return None, 0

        chunk_count = fresh.scalar(
            select(func.count())
            .select_from(DocumentChunk)
            .where(DocumentChunk.document_id == document.id)
        )

        return document.status, chunk_count

    finally:
        fresh.close()


def test_successful_ingestion_commits_chunks_and_status(
    database, fake_pdf, monkeypatch
) -> None:
    filename, pdf_bytes = fake_pdf
    monkeypatch.setattr(
        ingestion_service,
        "embed_texts",
        lambda texts: [[0.1] * 384 for _ in texts],
    )

    result = ingestion_service.ingest_pdf(
        database, filename=filename, pdf_bytes=pdf_bytes
    )

    assert result.page_count == 2
    assert read_state(filename) == ("indexed", result.chunk_count)


def test_crash_after_saving_chunks_leaves_no_chunks_behind(
    database, fake_pdf, monkeypatch
) -> None:
    filename, pdf_bytes = fake_pdf
    monkeypatch.setattr(
        ingestion_service,
        "embed_texts",
        lambda texts: [[0.1] * 384 for _ in texts],
    )

    real_create_chunks = ingestion_service.create_document_chunks

    def save_chunks_then_crash(*args, **kwargs):
        real_create_chunks(*args, **kwargs)
        raise RuntimeError("simulated crash after saving chunks")

    monkeypatch.setattr(
        ingestion_service, "create_document_chunks", save_chunks_then_crash
    )

    with pytest.raises(RuntimeError, match="simulated crash"):
        ingestion_service.ingest_pdf(
            database, filename=filename, pdf_bytes=pdf_bytes
        )

    assert read_state(filename) == ("failed", 0)


def test_database_error_is_recorded_as_failed(
    database, fake_pdf, monkeypatch
) -> None:
    filename, pdf_bytes = fake_pdf
    # 383 numbers instead of 384: PostgreSQL rejects the insert.
    monkeypatch.setattr(
        ingestion_service,
        "embed_texts",
        lambda texts: [[0.1] * 383 for _ in texts],
    )

    with pytest.raises(Exception) as error:
        ingestion_service.ingest_pdf(
            database, filename=filename, pdf_bytes=pdf_bytes
        )

    assert "PendingRollbackError" not in type(error.value).__name__
    assert read_state(filename) == ("failed", 0)