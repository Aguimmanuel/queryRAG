from dataclasses import dataclass
from hashlib import sha256

from queryrag.ingestion.parser import ParsedPage


@dataclass(frozen=True)
class TextChunk:
    chunk_id: str
    page_number: int
    chunk_index: int
    text: str
    metadata: dict[str, object]


def _stable_chunk_id(
    filename: str,
    page_number: int,
    chunk_index: int,
    text: str,
) -> str:
    raw_value = (
        f"{filename}:{page_number}:{chunk_index}:{text}"
    ).encode("utf-8")

    return sha256(raw_value).hexdigest()


def chunk_pages(
    pages: list[ParsedPage],
    *,
    chunk_size: int = 1200,
    overlap: int = 200,
) -> list[TextChunk]:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than zero")

    if overlap < 0 or overlap >= chunk_size:
        raise ValueError(
            "overlap must be at least zero and smaller than chunk_size"
        )

    chunks: list[TextChunk] = []

    for page in pages:
        text = " ".join(page.text.split())

        if not text:
            continue

        start = 0
        page_chunk_index = 0

        while start < len(text):
            end = min(start + chunk_size, len(text))
            chunk_text = text[start:end].strip()

            if chunk_text:
                chunk_id = _stable_chunk_id(
                    str(page.metadata.get("filename", "")),
                    page.page_number,
                    page_chunk_index,
                    chunk_text,
                )

                chunks.append(
                    TextChunk(
                        chunk_id=chunk_id,
                        page_number=page.page_number,
                        chunk_index=page_chunk_index,
                        text=chunk_text,
                        metadata={
                            **page.metadata,
                            "page_number": page.page_number,
                            "chunk_index": page_chunk_index,
                        },
                    )
                )

                page_chunk_index += 1

            if end >= len(text):
                break

            start = end - overlap

    return chunks
