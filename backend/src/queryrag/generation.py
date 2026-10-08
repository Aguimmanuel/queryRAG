from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from queryrag.schemas import AnswerResponse, Citation


class TextGenerator(Protocol):
    def generate(self, prompt: str) -> str:
        ...


@dataclass(frozen=True)
class Evidence:
    document_id: str
    filename: str
    page_number: int
    chunk_index: int
    text: str
    distance: float


def build_grounded_prompt(
    query: str,
    evidence: Sequence[Evidence],
) -> str:
    context = "\n\n".join(
        (
            f"Source: {item.filename}, page {item.page_number}\n"
            f"Evidence: {item.text}"
        )
        for item in evidence
    )

    return f"""Answer the user's question using only the evidence below.

If the evidence does not support an answer, say that there is
insufficient evidence. Do not invent facts.

User question:
{query}

Evidence:
{context}
"""


def generate_grounded_answer(
    query: str,
    evidence: Sequence[Evidence],
    generator: TextGenerator,
) -> AnswerResponse:
    if not evidence:
        return AnswerResponse(
            query=query,
            answer=(
                "Insufficient evidence in the indexed documents "
                "to answer that."
            ),
            citations=[],
            grounded=False,
            insufficient_evidence=True,
        )

    prompt = build_grounded_prompt(query, evidence)
    answer = generator.generate(prompt)

    citations = [
        Citation(
            document_id=item.document_id,
            filename=item.filename,
            page_number=item.page_number,
            chunk_index=item.chunk_index,
            distance=item.distance,
            text=item.text,
        )
        for item in evidence
    ]

    return AnswerResponse(
        query=query,
        answer=answer,
        citations=citations,
        grounded=True,
        insufficient_evidence=False,
    )