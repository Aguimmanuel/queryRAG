from dataclasses import dataclass
from typing import Any

import pymupdf
import pymupdf4llm


@dataclass(frozen=True)
class ParsedPage:
    page_number: int
    text: str
    metadata: dict[str, Any]


def parse_pdf_bytes(
    content: bytes,
    filename: str,
) -> list[ParsedPage]:
    document = pymupdf.open(
        stream=content,
        filetype="pdf",
    )

    try:
        page_chunks = pymupdf4llm.to_markdown(
            document,
            page_chunks=True,
        )
    finally:
        document.close()

    parsed_pages: list[ParsedPage] = []

    for index, page_chunk in enumerate(page_chunks):
        metadata = dict(page_chunk.get("metadata", {}))
        metadata["filename"] = filename

        parsed_pages.append(
            ParsedPage(
                page_number=index + 1,
                text=page_chunk.get("text", ""),
                metadata=metadata,
            )
        )

    return parsed_pages
