"""Scoring and reporting for the QueryRAG evaluation set.

Pure functions only: no HTTP, database or model calls. ``scripts/run_eval.py``
does the I/O and passes API payloads in, which keeps this module fast to
unit-test and reusable from other runners (e.g. CI).
"""

import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class EvalQuestion:
    """One labelled question from the eval dataset JSON."""

    id: str
    type: str
    question: str
    answerable: bool
    expected_pages: list[int]
    expected_keywords: list[str]


@dataclass(frozen=True)
class EvalResult:
    """Scored outcome for one question.

    Hit/match fields are ``None`` for unanswerable questions, where they do
    not apply, so they are excluded from rates rather than counted as misses.
    """

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
    # Populated when an API call failed; ``None`` for normally scored results.
    error: str | None = None


def load_questions(path: Path) -> tuple[dict, list[EvalQuestion]]:
    """Load a dataset file and split it into metadata and questions."""
    data = json.loads(path.read_text(encoding="utf-8"))
    questions = [EvalQuestion(**item) for item in data["questions"]]
    meta = {key: value for key, value in data.items() if key != "questions"}

    return meta, questions


def pages_from(items: list[dict], filename: str) -> list[int]:
    """Page numbers belonging to the eval document.

    Filtering by filename stops chunks from other indexed PDFs from being
    credited as hits on the expected pages.
    """
    return [item["page_number"] for item in items if item["filename"] == filename]


def is_abstention(query_payload: dict) -> bool:
    """Abstention is read from the API's structured flag, never from answer text.

    Free-text matching is brittle: models phrase refusals in many ways
    (see the q08 false negative in progress.md, 2026-11-15).
    """
    return bool(query_payload["insufficient_evidence"])


def score_question(
    question: EvalQuestion,
    search_payload: dict,
    query_payload: dict,
    latency_ms: float,
    filename: str,
) -> EvalResult:
    """Score one question from its ``/search`` and ``/query`` responses."""
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


def error_result(
    question: EvalQuestion,
    error: str,
    latency_ms: float,
) -> EvalResult:
    """Build a result for a question whose API call failed.

    A failure is always scored as incorrect behaviour. In particular it is
    never treated as an abstention: otherwise a crashing unanswerable question
    would silently inflate ``abstained_when_unanswerable``.
    """
    # Answerable questions count the failure as a miss on every metric;
    # unanswerable ones keep ``None`` so the metrics stay not-applicable.
    miss = False if question.answerable else None

    return EvalResult(
        id=question.id,
        type=question.type,
        answerable=question.answerable,
        retrieved_pages=[],
        top_distance=None,
        retrieval_hit=miss,
        cited_pages=[],
        citation_hit=miss,
        abstained=False,
        abstention_correct=False,
        keyword_match=miss,
        latency_ms=latency_ms,
        answer="",
        error=error,
    )


def _rate(values: list[bool]) -> str:
    """Format a list of booleans as ``passed/total``."""
    if not values:
        return "n/a"

    return f"{sum(values)}/{len(values)}"


def summarize(results: list[EvalResult]) -> dict[str, str]:
    """Aggregate per-question results into the report's summary metrics."""
    answerable = [r for r in results if r.answerable]
    unanswerable = [r for r in results if not r.answerable]
    # Failed calls are excluded: their duration reflects the failure (e.g. a
    # timeout or retries), not normal answer latency.
    latencies = sorted(r.latency_ms for r in results if r.error is None)

    return {
        "retrieval_hit": _rate([bool(r.retrieval_hit) for r in answerable]),
        "citation_hit": _rate([bool(r.citation_hit) for r in answerable]),
        "keyword_match": _rate([bool(r.keyword_match) for r in answerable]),
        "answered_when_answerable": _rate([r.abstention_correct for r in answerable]),
        "abstained_when_unanswerable": _rate(
            [r.abstention_correct for r in unanswerable]
        ),
        # Upper median for even counts; good enough for a small smoke-test set.
        "median_latency_ms": (
            f"{latencies[len(latencies) // 2]:.0f}" if latencies else "n/a"
        ),
        "errors": str(sum(1 for r in results if r.error is not None)),
    }


def _mark(value: bool | None) -> str:
    """Render a tri-state metric for the Markdown table."""
    if value is None:
        return "–"

    return "✅" if value else "❌"


def render_markdown(
    meta: dict,
    results: list[EvalResult],
    summary: dict[str, str],
    settings: dict[str, object],
) -> str:
    """Render a human-readable report suitable for committing to the repo."""
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

    # Failed questions show their error so the cause is visible in the report.
    lines += ["", "## Answers", ""]
    lines += [
        f"- **{r.id}**: ERROR: {r.error}" if r.error else f"- **{r.id}**: {r.answer}"
        for r in results
    ]

    return "\n".join(lines) + "\n"


def results_to_json(results: list[EvalResult]) -> str:
    """Serialize results for machine comparison between runs."""
    return json.dumps([asdict(r) for r in results], indent=2)
