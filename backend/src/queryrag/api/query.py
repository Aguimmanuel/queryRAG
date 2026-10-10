import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from queryrag.database import get_db
from queryrag.embeddings import embed_query
from queryrag.generation import (
    Evidence,
    GenerationProviderError,
    TextGenerator,
    generate_grounded_answer,
)
from queryrag.models import Document
from queryrag.providers.gemini import create_gemini_generator
from queryrag.repositories.chunks import search_document_chunks
from queryrag.schemas import AnswerRequest, AnswerResponse

logger = logging.getLogger("queryrag.query")
router = APIRouter(
    prefix="/query",
    tags=["query"],
)


def get_text_generator() -> TextGenerator:
    try:
        return create_gemini_generator()
    except GenerationProviderError as error:
        logger.warning("Answer provider not configured: %s", error)
        raise HTTPException(
            status_code=503,
            detail="Answer generation is not configured",
        ) from error


def retrieve_evidence(
    database: Session,
    query: str,
    limit: int,
) -> list[Evidence]:
    query_embedding = embed_query(query)

    matches = search_document_chunks(
        database,
        query_embedding,
        limit=limit,
    )

    evidence = []

    for chunk, distance in matches:
        document = database.get(Document, chunk.document_id)

        if document is None:
            continue

        evidence.append(
            Evidence(
                document_id=str(chunk.document_id),
                filename=document.filename,
                page_number=chunk.page_number,
                chunk_index=chunk.chunk_index,
                text=chunk.text,
                distance=distance,
            )
        )

    return evidence


@router.post("", response_model=AnswerResponse)
def query_endpoint(
    payload: AnswerRequest,
    database: Session = Depends(get_db),
    generator: TextGenerator = Depends(get_text_generator),
) -> AnswerResponse:
    evidence = retrieve_evidence(database, payload.query, payload.limit)

    try:
        return generate_grounded_answer(payload.query, evidence, generator)
    except GenerationProviderError as error:
        logger.warning("Answer provider failed: %s", error)
        raise HTTPException(
            status_code=502,
            detail="The answer provider failed. Please try again.",
        ) from error
