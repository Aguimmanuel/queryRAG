from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from queryrag.api import query as query_api
from queryrag.database import get_db
from queryrag.generation import Evidence, GenerationProviderError
from queryrag.main import app

SAMPLE_EVIDENCE = [
    Evidence(
        document_id=str(uuid4()),
        filename="sample.pdf",
        page_number=2,
        chunk_index=0,
        text="QueryRAG preserves document and page provenance.",
        distance=0.12,
    )
]


class FakeGenerator:
    def __init__(self, answer: str = "It preserves page provenance.") -> None:
        self.answer = answer
        self.calls = 0

    def generate(self, prompt: str) -> str:
        self.calls += 1
        return self.answer


class FailingGenerator:
    def generate(self, prompt: str) -> str:
        raise GenerationProviderError("Gemini returned HTTP 503")


@pytest.fixture
def client():
    def override_get_db():
        yield None

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


def use_generator(generator) -> None:
    app.dependency_overrides[query_api.get_text_generator] = lambda: generator


def use_evidence(monkeypatch: pytest.MonkeyPatch, evidence: list[Evidence]) -> None:
    monkeypatch.setattr(
        query_api,
        "retrieve_evidence",
        lambda database, query, limit: evidence,
    )


def test_query_returns_grounded_answer_with_citations(client, monkeypatch) -> None:
    generator = FakeGenerator()
    use_generator(generator)
    use_evidence(monkeypatch, SAMPLE_EVIDENCE)

    response = client.post("/query", json={"query": "What is preserved?"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["grounded"] is True
    assert payload["insufficient_evidence"] is False
    assert payload["answer"] == "It preserves page provenance."
    assert payload["citations"][0]["filename"] == "sample.pdf"
    assert payload["citations"][0]["page_number"] == 2
    assert generator.calls == 1


def test_query_without_evidence_does_not_call_provider(client, monkeypatch) -> None:
    generator = FakeGenerator()
    use_generator(generator)
    use_evidence(monkeypatch, [])

    response = client.post("/query", json={"query": "Weather on Mars?"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["grounded"] is False
    assert payload["insufficient_evidence"] is True
    assert payload["citations"] == []
    assert generator.calls == 0


def test_query_provider_failure_returns_502(client, monkeypatch, caplog) -> None:
    use_generator(FailingGenerator())
    use_evidence(monkeypatch, SAMPLE_EVIDENCE)

    with caplog.at_level("WARNING", logger="queryrag.query"):
        response = client.post("/query", json={"query": "What is preserved?"})

    assert "Answer provider failed: Gemini returned HTTP 503" in caplog.text

    assert response.status_code == 502
    assert response.json() == {
        "detail": "The answer provider failed. Please try again."
    }


def test_query_without_provider_configuration_returns_503(client, monkeypatch) -> None:
    def missing_key():
        raise GenerationProviderError("GEMINI_API_KEY is required")

    monkeypatch.setattr(query_api, "create_gemini_generator", missing_key)
    use_evidence(monkeypatch, SAMPLE_EVIDENCE)

    response = client.post("/query", json={"query": "What is preserved?"})

    assert response.status_code == 503
    assert response.json() == {"detail": "Answer generation is not configured"}


def test_query_rejects_empty_question(client) -> None:
    use_generator(FakeGenerator())

    response = client.post("/query", json={"query": ""})

    assert response.status_code == 422
