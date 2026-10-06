from pathlib import Path

from queryrag.database import get_session_factory
from queryrag.ingestion.service import ingest_pdf


def main() -> None:
    pdf_path = Path("samples/sample.pdf")
    database = get_session_factory()()

    try:
        result = ingest_pdf(
            database,
            filename=pdf_path.name,
            pdf_bytes=pdf_path.read_bytes(),
        )

        print(f"Document ID: {result.document_id}")
        print(f"Pages indexed: {result.page_count}")
        print(f"Chunks indexed: {result.chunk_count}")

    finally:
        database.close()


if __name__ == "__main__":
    main()
