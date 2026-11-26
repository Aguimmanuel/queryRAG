from queryrag.main import app
from queryrag.openapi_contract import CONTRACT_PATH, render_openapi_yaml

EXPORT_HINT = (
    "docs/api/openapi.yaml is out of date. From the project root run: "
    "uv run --project backend python scripts/export_openapi.py"
)


def test_committed_contract_matches_the_app() -> None:
    assert CONTRACT_PATH.exists(), EXPORT_HINT
    committed = CONTRACT_PATH.read_text(encoding="utf-8")

    assert committed == render_openapi_yaml(app), EXPORT_HINT


def documented_statuses(path: str, method: str) -> set[str]:
    return set(app.openapi()["paths"][path][method]["responses"])


def test_upload_documents_every_error() -> None:
    assert {"201", "400", "409", "413", "415", "422"} <= documented_statuses(
        "/documents/upload", "post"
    )


def test_document_routes_document_not_found() -> None:
    assert "404" in documented_statuses("/documents/{document_id}", "get")
    assert "404" in documented_statuses("/documents/{document_id}", "delete")


def test_query_documents_provider_errors() -> None:
    assert {"200", "502", "503"} <= documented_statuses("/query", "post")


def test_ready_documents_not_ready() -> None:
    assert {"200", "503"} <= documented_statuses("/ready", "get")
