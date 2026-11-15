from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from queryrag.schemas import AnswerResponse, Citation

INSUFFICIENT_EVIDENCE_MESSAGE = (
    "Insufficient evidence in the indexed documents to answer that."
)
ABSTAIN_TOKEN = "INSUFFICIENT_EVIDENCE"


class GenerationProviderError(RuntimeError):
    """Raised when an external text-generation provider fails."""


class TextGenerator(Protocol):
    def generate(self, prompt: str) -> str: ...


@dataclass(frozen=True)
class Evidence:
    document_id: str
    filename: str
    page_number: int
    chunk_index: int
    text: str
    distance: float


def filter_relevant_evidence(
    evidence: Sequence[Evidence],
    max_distance: float,
) -> list[Evidence]:
    return [item for item in evidence if item.distance <= max_distance]


def build_grounded_prompt(
    query: str,
    evidence: Sequence[Evidence],
) -> str:
    context = "\n\n".join(
        (f"Source: {item.filename}, page {item.page_number}\nEvidence: {item.text}")
        for item in evidence
    )

    return f"""You answer questions using only the evidence below.

Rules:
- Use only facts that are stated in the evidence.
- The evidence may use different words than the question. If it contains
  the information needed to answer, answer the question.
- Do not use outside knowledge, even if you know the answer.
- If the evidence does not contain the information needed to answer,
  reply with exactly {ABSTAIN_TOKEN} and nothing else.
- Do not invent facts.

User question:
{query}

Evidence:
{context}
"""


def is_abstention_reply(answer: str) -> bool:
    return ABSTAIN_TOKEN in answer.upper()


def insufficient_evidence_response(query: str) -> AnswerResponse:
    return AnswerResponse(
        query=query,
        answer=INSUFFICIENT_EVIDENCE_MESSAGE,
        citations=[],
        grounded=False,
        insufficient_evidence=True,
    )


def generate_grounded_answer(
    query: str,
    evidence: Sequence[Evidence],
    generator: TextGenerator,
) -> AnswerResponse:
    if not evidence:
        return insufficient_evidence_response(query)

    prompt = build_grounded_prompt(query, evidence)
    answer = generator.generate(prompt)

    if is_abstention_reply(answer):
        return insufficient_evidence_response(query)

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
