from queryrag.evaluation import EvalQuestion, score_question, summarize

FILENAME = "cfpb_efta_faqs.pdf"


def make_question(answerable: bool = True) -> EvalQuestion:
    return EvalQuestion(
        id="q01",
        type="direct",
        question="Can P2P payments be EFTs?",
        answerable=answerable,
        expected_pages=[2] if answerable else [],
        expected_keywords=["yes"] if answerable else [],
    )


def search_payload(pages: list[int], distance: float = 0.2) -> dict:
    return {
        "results": [
            {"filename": FILENAME, "page_number": page, "distance": distance}
            for page in pages
        ]
    }


def query_payload(answer: str, pages: list[int], insufficient: bool = False) -> dict:
    return {
        "answer": answer,
        "citations": [{"filename": FILENAME, "page_number": page} for page in pages],
        "insufficient_evidence": insufficient,
    }


def test_answerable_question_scores_hits() -> None:
    result = score_question(
        make_question(),
        search_payload([2, 3]),
        query_payload("Yes, P2P payments can be EFTs.", [2]),
        latency_ms=1200,
        filename=FILENAME,
    )

    assert result.retrieval_hit is True
    assert result.citation_hit is True
    assert result.keyword_match is True
    assert result.abstention_correct is True


def test_answerable_question_misses_wrong_page() -> None:
    result = score_question(
        make_question(),
        search_payload([7, 9]),
        query_payload("Yes.", [7]),
        latency_ms=1000,
        filename=FILENAME,
    )

    assert result.retrieval_hit is False
    assert result.citation_hit is False


def test_pages_from_other_documents_are_ignored() -> None:
    payload = {
        "results": [{"filename": "sample.pdf", "page_number": 2, "distance": 0.1}]
    }

    result = score_question(
        make_question(),
        payload,
        query_payload("Yes.", []),
        latency_ms=1000,
        filename=FILENAME,
    )

    assert result.retrieval_hit is False


def test_unanswerable_counts_text_abstention_as_correct() -> None:
    result = score_question(
        make_question(answerable=False),
        search_payload([2], distance=0.35),
        query_payload("There is insufficient evidence to answer.", [2]),
        latency_ms=900,
        filename=FILENAME,
    )

    assert result.abstained is True
    assert result.abstention_correct is True
    assert result.retrieval_hit is None


def test_unanswerable_answered_is_incorrect() -> None:
    result = score_question(
        make_question(answerable=False),
        search_payload([2], distance=0.35),
        query_payload("The limit is $50.", [2]),
        latency_ms=900,
        filename=FILENAME,
    )

    assert result.abstention_correct is False


def test_summarize_reports_rates() -> None:
    answered = score_question(
        make_question(),
        search_payload([2]),
        query_payload("Yes.", [2]),
        latency_ms=1000,
        filename=FILENAME,
    )
    abstained = score_question(
        make_question(answerable=False),
        search_payload([]),
        query_payload("Insufficient evidence.", [], insufficient=True),
        latency_ms=10,
        filename=FILENAME,
    )

    summary = summarize([answered, abstained])

    assert summary["retrieval_hit"] == "1/1"
    assert summary["abstained_when_unanswerable"] == "1/1"
