from pathlib import Path

import pymupdf


output_path = Path("samples/sample.pdf")
output_path.parent.mkdir(parents=True, exist_ok=True)

document = pymupdf.open()

page_one = document.new_page()
page_one.insert_text(
    (72, 72),
    "QueryRAG Sample Knowledge Document\n\n"
    "QueryRAG is a document-grounded retrieval system. "
    "It retrieves relevant evidence from source documents before "
    "generating an answer.\n\n"
    "The system preserves document and page provenance so users "
    "can inspect the evidence behind an answer.",
    fontsize=12,
)

page_two = document.new_page()
page_two.insert_text(
    (72, 72),
    "Retrieval Notes\n\n"
    "Dense retrieval finds semantically related passages. "
    "Keyword retrieval finds exact names, identifiers, dates "
    "and technical terms.\n\n"
    "A hybrid retriever combines both approaches. QueryRAG will "
    "eventually use PostgreSQL full-text search, pgvector and "
    "reciprocal rank fusion.",
    fontsize=12,
)

page_three = document.new_page()
page_three.insert_text(
    (72, 72),
    "Testing Notes\n\n"
    "A reliable RAG system should test parsing, chunking, retrieval, "
    "citations, insufficient-evidence behavior and database recovery.\n\n"
    "This sample document is intended for local development only.",
    fontsize=12,
)

document.save(output_path)
document.close()

print(f"Created: {output_path.resolve()}")
