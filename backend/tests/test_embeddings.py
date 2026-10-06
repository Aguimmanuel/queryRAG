import os

import pytest

from queryrag.embeddings import (
    MODEL_ID,
    VECTOR_DIMENSION,
    embed_query,
)


@pytest.mark.embedding
@pytest.mark.skipif(
    os.getenv("RUN_EMBEDDING_TESTS") != "1",
    reason="Set RUN_EMBEDDING_TESTS=1 to run model tests",
)
def test_embedding_model_profile() -> None:
    vector = embed_query("QueryRAG embedding test")

    assert MODEL_ID == "BAAI/bge-small-en-v1.5"
    assert len(vector) == VECTOR_DIMENSION
    assert all(isinstance(value, float) for value in vector)
