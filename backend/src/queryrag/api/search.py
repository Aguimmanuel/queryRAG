from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from queryrag.database import get_db
from queryrag.embeddings import embed_query
from queryrag.models import Document
from queryrag.repositories.chunks import search_document_chunks
from queryrag.schemas import SearchRequest, SearchResponse, SearchResult

router = APIRouter(
    prefix="/search",
    tags=["search"],
)


@router.post("", response_model=SearchResponse)
def search_endpoint(
    payload: SearchRequest,
    database: Session = Depends(get_db),
) -> SearchResponse:
    query_embedding = embed_query(payload.query)

    matches = search_document_chunks(
        database,
        query_embedding,
        limit=payload.limit,
    )

    results = []

    for chunk, distance in matches:
        document = database.get(Document, chunk.document_id)

        if document is None:
            continue

        results.append(
            SearchResult(
                document_id=chunk.document_id,
                filename=document.filename,
                page_number=chunk.page_number,
                chunk_index=chunk.chunk_index,
                text=chunk.text,
                distance=distance,
            )
        )

    return SearchResponse(
        query=payload.query,
        results=results,
    )