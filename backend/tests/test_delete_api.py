from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from queryrag.api import documents as documents_api
from queryrag.database import get_db
from queryrag.main import app


class FakeSession:
    def __init__(self) -> None:
        self.committed = False

    def commit(self) -> None:
        self.committed = True


@pytest.fixture
def session():
    fake = FakeSession()

    def override_get_db():
        yield fake

    app.dependency_overrides[get_db] = override_get_db
    yield fake
    app.dependency_overrides.clear()


def test_delete_returns_204_and_commits(session, monkeypatch) -> None:
    document = SimpleNamespace(id=uuid4(), filename="report.pdf")
    deleted = []

    monkeypatch.setattr(documents_api, "get_document", lambda db, doc_id: document)
    monkeypatch.setattr(
        documents_api, "delete_document", lambda db, doc: deleted.append(doc)
    )

    response = TestClient(app).delete(f"/documents/{document.id}")

    assert response.status_code == 204
    assert response.content == b""
    assert deleted == [document]
    assert session.committed is True


def test_delete_unknown_document_returns_404(session, monkeypatch) -> None:
    monkeypatch.setattr(documents_api, "get_document", lambda db, doc_id: None)
    monkeypatch.setattr(documents_api, "delete_document", pytest.fail)

    response = TestClient(app).delete(f"/documents/{uuid4()}")

    assert response.status_code == 404
    assert response.json() == {"detail": "Document not found"}
    assert session.committed is False


def test_delete_rejects_invalid_id(session) -> None:
    response = TestClient(app).delete("/documents/not-a-uuid")

    assert response.status_code == 422
