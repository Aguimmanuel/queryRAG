import pymupdf
from queryrag.ingestion.parser import parse_pdf_bytes


def create_sample_pdf() -> bytes:
    document = pymupdf.open()

    first_page = document.new_page()
    first_page.insert_text(
        (72, 72),
        "QueryRAG is a document-grounded retrieval system.",
    )

    second_page = document.new_page()
    second_page.insert_text(
        (72, 72),
        "This page exists to verify page-level provenance.",
    )

    content = document.tobytes()
    document.close()

    return content


def test_parse_pdf_preserves_page_provenance() -> None:
    pages = parse_pdf_bytes(
        create_sample_pdf(),
        "sample.pdf",
    )

    assert len(pages) == 2
    assert pages[0].page_number == 1
    assert pages[1].page_number == 2
    assert "document-grounded" in pages[0].text
    assert "page-level provenance" in pages[1].text
    assert pages[0].metadata["filename"] == "sample.pdf"
