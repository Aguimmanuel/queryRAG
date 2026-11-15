import json
from dataclasses import asdict, dataclass
from pathlib import Path

ABSTAIN_PHRASE = "insufficient evidence"


@dataclass(frozen=True)
class EvalQuestion:
    id: str
    type: str
    question: str
    answerable: bool
    expected_pages: list[int]
    expected_keywords: list[str]


@dataclass(frozen=True)
class EvalResult:
    id: str
    type: str
    answerable: bool
    retrieved_pages: list[int]
    top_distance: float | None
    retrieval_hit: bool | None
    cited_pages: list[int]
    citation_hit: bool | None
    abstained: bool
    abstention_correct: bool
    keyword_match: bool | None
    latency_ms: float
    answer: str


def load_questions(path: Path) -> tuple[dict, list[EvalQuestion]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    questions = [EvalQuestion(**item) for item in data["questions"]]
    meta = {key: value for key, value in data.items() if key != "questions"}

    return meta, questions


def pages_from(items: list[dict], filename: str) -> list[int]:
    return [item["page_number"] for item in items if item["filename"] == filename]


def is_abstention(query_payload: dict) -> bool:
    return bool(query_payload["insufficient_evidence"]) or (
        ABSTAIN_PHRASE in query_payload["answer"].lower()
    )


def score_question(
    question: EvalQuestion,
    search_payload: dict,
    query_payload: dict,
    latency_ms: float,
    filename: str,
) -> EvalResult:
    search_results = search_payload["results"]
    retrieved_pages = pages_from(search_results, filename)
    cited_pages = pages_from(query_payload["citations"], filename)
    abstained = is_abstention(query_payload)
    answer = query_payload["answer"]

    expected = set(question.expected_pages)

    if question.answerable:
        retrieval_hit = bool(expected & set(retrieved_pages))
        citation_hit = bool(expected & set(cited_pages))
        keyword_match = all(
            keyword.lower() in answer.lower() for keyword in question.expected_keywords
        )
        abstention_correct = not abstained
    else:
        retrieval_hit = None
        citation_hit = None
        keyword_match = None
        abstention_correct = abstained

    return EvalResult(
        id=question.id,
        type=question.type,
        answerable=question.answerable,
        retrieved_pages=retrieved_pages,
        top_distance=search_results[0]["distance"] if search_results else None,
        retrieval_hit=retrieval_hit,
        cited_pages=cited_pages,
        citation_hit=citation_hit,
        abstained=abstained,
        abstention_correct=abstention_correct,
        keyword_match=keyword_match,
        latency_ms=latency_ms,
        answer=answer,
    )


def _rate(values: list[bool]) -> str:
    if not values:
        return "n/a"

    return f"{sum(values)}/{len(values)}"


def summarize(results: list[EvalResult]) -> dict[str, str]:
    answerable = [r for r in results if r.answerable]
    unanswerable = [r for r in results if not r.answerable]
    latencies = sorted(r.latency_ms for r in results)

    return {
        "retrieval_hit": _rate([bool(r.retrieval_hit) for r in answerable]),
        "citation_hit": _rate([bool(r.citation_hit) for r in answerable]),
        "keyword_match": _rate([bool(r.keyword_match) for r in answerable]),
        "answered_when_answerable": _rate([r.abstention_correct for r in answerable]),
        "abstained_when_unanswerable": _rate(
            [r.abstention_correct for r in unanswerable]
        ),
        "median_latency_ms": (
            f"{latencies[len(latencies) // 2]:.0f}" if latencies else "n/a"
        ),
    }


def _mark(value: bool | None) -> str:
    if value is None:
        return "–"

    return "✅" if value else "❌"


def render_markdown(
    meta: dict,
    results: list[EvalResult],
    summary: dict[str, str],
    settings: dict[str, object],
) -> str:
    lines = [
        f"# Evaluation report — {meta['dataset']}",
        "",
        f"- Document: `{meta['document']}`",
        *[f"- {key}: `{value}`" for key, value in settings.items()],
        "",
        "## Summary",
        "",
        "| Metric | Result |",
        "|---|---|",
        *[f"| {key} | {value} |" for key, value in summary.items()],
        "",
        "## Per question",
        "",
        "| ID | Type | Top distance | Retrieved pages | Retrieval | Cited pages "
        "| Citation | Keywords | Abstained | Correct behaviour | Latency ms |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]

    for r in results:
        distance = f"{r.top_distance:.3f}" if r.top_distance is not None else "–"
        lines.append(
            f"| {r.id} | {r.type} | {distance} | {r.retrieved_pages} "
            f"| {_mark(r.retrieval_hit)} | {r.cited_pages} | {_mark(r.citation_hit)} "
            f"| {_mark(r.keyword_match)} | {r.abstained} "
            f"| {_mark(r.abstention_correct)} | {r.latency_ms:.0f} |"
        )

    lines += ["", "## Answers", ""]
    lines += [f"- **{r.id}**: {r.answer}" for r in results]

    return "\n".join(lines) + "\n"


def results_to_json(results: list[EvalResult]) -> str:
    return json.dumps([asdict(r) for r in results], indent=2)
