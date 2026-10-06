from queryrag.ingestion.chunking import chunk_pages
from queryrag.ingestion.parser import ParsedPage


def test_chunk_pages_preserves_page_metadata() -> None:
    page = ParsedPage(
        page_number=3,
        text="word " * 100,
        metadata={"filename": "sample.pdf"},
    )

    chunks = chunk_pages(
        [page],
        chunk_size=100,
        overlap=20,
    )

    assert len(chunks) > 1
    assert all(chunk.page_number == 3 for chunk in chunks)
    assert all(chunk.metadata["filename"] == "sample.pdf" for chunk in chunks)
    assert all(chunk.chunk_id for chunk in chunks)


def test_chunk_pages_rejects_invalid_overlap() -> None:
    page = ParsedPage(
        page_number=1,
        text="Some text",
        metadata={"filename": "sample.pdf"},
    )

    try:
        chunk_pages([page], chunk_size=100, overlap=100)
    except ValueError as error:
        assert "overlap" in str(error)
    else:
        raise AssertionError("Expected ValueError")
