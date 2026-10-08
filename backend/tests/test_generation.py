from uuid import uuid4

from queryrag.generation import (
    Evidence,
    generate_grounded_answer,
)


class FakeGenerator:
    def __init__(self) -> None:
        self.received_prompt = ""

    def generate(self, prompt: str) -> str:
        self.received_prompt = prompt
        return "QueryRAG preserves document and page provenance."


def test_generation_returns_grounded_answer_with_citation() -> None:
    generator = FakeGenerator()
    document_id = str(uuid4())

    evidence = [
        Evidence(
            document_id=document_id,
            filename="sample.pdf",
            page_number=1,
            chunk_index=0,
            text=(
                "The system preserves document and page provenance "
                "so users can inspect the evidence."
            ),
            distance=0.19,
        )
    ]

    response = generate_grounded_answer(
        "What does QueryRAG preserve?",
        evidence,
        generator,
    )

    assert response.grounded is True
    assert response.insufficient_evidence is False
    assert response.answer == (
        "QueryRAG preserves document and page provenance."
    )
    assert len(response.citations) == 1
    assert response.citations[0].filename == "sample.pdf"
    assert response.citations[0].page_number == 1
    assert "What does QueryRAG preserve?" in generator.received_prompt


def test_generation_refuses_to_invent_without_evidence() -> None:
    generator = FakeGenerator()

    response = generate_grounded_answer(
        "What is the weather on Mars today?",
        [],
        generator,
    )

    assert response.grounded is False
    assert response.insufficient_evidence is True
    assert response.citations == []
    assert "insufficient evidence" in response.answer.lower()
