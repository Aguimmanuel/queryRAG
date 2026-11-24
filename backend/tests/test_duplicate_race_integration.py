"""Two uploads of the same PDF at the same moment (a "race").

The API checks for an existing hash first, but two requests can both pass that
check before either one saves. The UNIQUE constraint on documents.content_hash
then rejects the second INSERT. These tests skip the API check on purpose and
call the service directly, which is exactly the losing request's situation.
"""

import os
from hashlib import sha256
from uuid import uuid4

import pytest
from queryrag.config import get_settings
from queryrag.database import get_session_factory
from queryrag.ingestion import service as ingestion_service
from queryrag.ingestion.service import DuplicateDocumentError
from queryrag.models import Document
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
def pdf_bytes():
    content = f"%PDF-race-{uuid4().hex}".encode()

    yield content

    cleanup = get_session_factory()()
    cleanup.execute(
        delete(Document).where(Document.content_hash == sha256(content).hexdigest())
    )
    cleanup.commit()
    cleanup.close()


def save_winner(pdf_bytes: bytes) -> Document:
    """The request that won the race: its row is already committed."""
    session = get_session_factory()()

    try:
        winner = Document(
            filename="winner.pdf",
            content_type="application/pdf",
            content_hash=sha256(pdf_bytes).hexdigest(),
            status="indexed",
        )
        session.add(winner)
        session.commit()
        session.refresh(winner)
        session.expunge(winner)

        return winner

    finally:
        session.close()


def count_rows(pdf_bytes: bytes) -> int:
    fresh = get_session_factory()()

    try:
        return fresh.scalar(
            select(func.count())
            .select_from(Document)
            .where(Document.content_hash == sha256(pdf_bytes).hexdigest())
        )

    finally:
        fresh.close()


def test_losing_upload_raises_duplicate_with_winner_id(database, pdf_bytes) -> None:
    winner = save_winner(pdf_bytes)

    with pytest.raises(DuplicateDocumentError) as error:
        ingestion_service.ingest_pdf(
            database, filename="loser.pdf", pdf_bytes=pdf_bytes
        )

    assert error.value.document_id == winner.id
    assert error.value.status == "indexed"
    assert count_rows(pdf_bytes) == 1  # the database kept exactly one copy


def test_session_is_still_usable_after_duplicate(database, pdf_bytes) -> None:
    save_winner(pdf_bytes)

    with pytest.raises(DuplicateDocumentError):
        ingestion_service.ingest_pdf(
            database, filename="loser.pdf", pdf_bytes=pdf_bytes
        )

    # No PendingRollbackError: the service rolled the session back.
    assert database.scalar(select(func.count()).select_from(Document)) >= 1