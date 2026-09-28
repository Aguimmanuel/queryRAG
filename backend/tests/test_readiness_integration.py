import os

import pytest
from fastapi.testclient import TestClient
from queryrag.main import app

client = TestClient(app)


@pytest.mark.integration
def test_ready_with_database() -> None:
    if not os.getenv("DATABASE_URL"):
        pytest.skip("DATABASE_URL is required for the integration test")

    response = client.get("/ready")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "database": "ok",
    }
