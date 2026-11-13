from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from queryrag.api import documents as documents_api
from queryrag.config import Settings
from queryrag.database import get_db
from queryrag.ingestion.service import IngestionResult
from queryrag.main import app

FAKE_PDF = b"%PDF-1.4 fake pdf content for tests"


@pytest.fixture
def client(monkeypatch):
    def override_get_db():
        yield None

    app.dependency_overrides[get_db] = override_get_db
    monkeypatch.setattr(documents_api, "get_document_by_hash", lambda db, h: None)
    yield TestClient(app)
    app.dependency_overrides.clear()


def upload(client, content: bytes, filename: str = "report.pdf"):
    return client.post(
        "/documents/upload",
        files={"file": (filename, content, "application/pdf")},
    )


def test_upload_indexes_pdf(client, monkeypatch) -> None:
    calls = []
    document_id = uuid4()

    def fake_ingest(database, *, filename, pdf_bytes):
        calls.append((filename, pdf_bytes))
        return IngestionResult(document_id=document_id, page_count=3, chunk_count=3)

    monkeypatch.setattr(documents_api, "ingest_pdf", fake_ingest)

    response = upload(client, FAKE_PDF)

    assert response.status_code == 201
    assert response.json() == {
        "document_id": str(document_id),
        "filename": "report.pdf",
        "status": "indexed",
        "page_count": 3,
        "chunk_count": 3,
    }
    assert calls == [("report.pdf", FAKE_PDF)]


def test_upload_rejects_non_pdf(client, monkeypatch) -> None:
    monkeypatch.setattr(documents_api, "ingest_pdf", pytest.fail)

    response = upload(client, b"hello, not a pdf", filename="notes.txt")

    assert response.status_code == 415


def test_upload_rejects_empty_file(client) -> None:
    response = upload(client, b"")

    assert response.status_code == 400


def test_upload_rejects_file_over_size_limit(client, monkeypatch) -> None:
    monkeypatch.setattr(
        documents_api, "get_settings", lambda: Settings(max_upload_mb=1)
    )

    response = upload(client, b"%PDF-" + b"0" * (1024 * 1024))

    assert response.status_code == 413


def test_upload_rejects_duplicate(client, monkeypatch) -> None:
    existing = SimpleNamespace(id=uuid4(), status="indexed")
    monkeypatch.setattr(
        documents_api, "get_document_by_hash", lambda db, h: existing
    )
    monkeypatch.setattr(documents_api, "ingest_pdf", pytest.fail)

    response = upload(client, FAKE_PDF)

    assert response.status_code == 409
    assert response.json()["detail"]["document_id"] == str(existing.id)


def test_upload_returns_422_when_pdf_cannot_be_processed(client, monkeypatch) -> None:
    def broken_ingest(database, *, filename, pdf_bytes):
        raise ValueError("cannot parse")

    monkeypatch.setattr(documents_api, "ingest_pdf", broken_ingest)

    response = upload(client, FAKE_PDF)

    assert response.status_code == 422
    assert response.json() == {"detail": "The PDF could not be processed"}