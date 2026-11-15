from uuid import uuid4

from queryrag.generation import (
    ABSTAIN_TOKEN,
    INSUFFICIENT_EVIDENCE_MESSAGE,
    Evidence,
    build_grounded_prompt,
    filter_relevant_evidence,
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



def make_evidence(distance: float) -> Evidence:
    return Evidence(
        document_id=str(uuid4()),
        filename="sample.pdf",
        page_number=1,
        chunk_index=0,
        text="Some evidence.",
        distance=distance,
    )


def test_filter_keeps_only_evidence_within_max_distance() -> None:
    evidence = [make_evidence(0.2), make_evidence(0.5), make_evidence(0.7)]

    relevant = filter_relevant_evidence(evidence, max_distance=0.5)

    assert [item.distance for item in relevant] == [0.2, 0.5]


class AbstainingGenerator:
    def __init__(self, reply: str) -> None:
        self.reply = reply
        self.calls = 0

    def generate(self, prompt: str) -> str:
        self.calls += 1
        return self.reply


def test_model_abstention_sets_insufficient_evidence_flags() -> None:
    generator = AbstainingGenerator(ABSTAIN_TOKEN)

    response = generate_grounded_answer(
        "What is the maximum liability?",
        [make_evidence(0.3)],
        generator,
    )

    assert generator.calls == 1
    assert response.grounded is False
    assert response.insufficient_evidence is True
    assert response.citations == []
    assert response.answer == INSUFFICIENT_EVIDENCE_MESSAGE


def test_abstention_token_is_detected_inside_a_longer_reply() -> None:
    generator = AbstainingGenerator("insufficient_evidence.")

    response = generate_grounded_answer(
        "What fees apply?",
        [make_evidence(0.3)],
        generator,
    )

    assert response.insufficient_evidence is True


def test_prompt_forbids_outside_knowledge_and_names_the_token() -> None:
    prompt = build_grounded_prompt("Question?", [make_evidence(0.2)])

    assert "outside knowledge" in prompt
    assert ABSTAIN_TOKEN in prompt