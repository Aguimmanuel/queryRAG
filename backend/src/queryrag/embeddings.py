from functools import lru_cache

from fastembed import TextEmbedding

MODEL_ID = "BAAI/bge-small-en-v1.5"
VECTOR_DIMENSION = 384


@lru_cache
def get_embedding_model() -> TextEmbedding:
    return TextEmbedding(model_name=MODEL_ID)


def embed_texts(texts: list[str]) -> list[list[float]]:
    model = get_embedding_model()

    return [
        vector.tolist()
        for vector in model.embed(texts)
    ]


def embed_query(query: str) -> list[float]:
    return embed_texts([query])[0]
