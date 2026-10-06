import sys
from pathlib import Path

from queryrag.ingestion.chunking import chunk_pages
from queryrag.ingestion.parser import parse_pdf_bytes


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit(
            "Usage: python scripts/inspect_pdf.py <path-to-pdf>"
        )

    pdf_path = Path(sys.argv[1])

    if not pdf_path.exists():
        raise SystemExit(f"PDF not found: {pdf_path}")

    pages = parse_pdf_bytes(
        pdf_path.read_bytes(),
        pdf_path.name,
    )

    chunks = chunk_pages(pages)

    print(f"File: {pdf_path}")
    print(f"Pages parsed: {len(pages)}")
    print(f"Chunks created: {len(chunks)}")
    print()

    for page in pages:
        print(
            f"Page {page.page_number}: "
            f"{len(page.text)} extracted characters"
        )

    print()

    for chunk in chunks:
        preview = " ".join(chunk.text.split())[:160]

        print(
            f"Chunk {chunk.chunk_index} "
            f"(page {chunk.page_number})"
        )
        print(f"  ID: {chunk.chunk_id[:16]}...")
        print(f"  Characters: {len(chunk.text)}")
        print(f"  Preview: {preview}")
        print()


if __name__ == "__main__":
    main()
