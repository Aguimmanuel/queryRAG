"""Run the QueryRAG evaluation set against a running API.

Usage (from the project root, with the server running):
    uv run --project backend python scripts/run_eval.py --label my-run

For each question the script calls ``/search`` (to score retrieval) and
``/query`` (to score the answer), then writes a Markdown and a JSON report to
``eval/results/``.

A failed API call does not abort the run: the question is recorded as an
error and scored as incorrect. The process exits with status 1 if any errors
occurred, so CI can treat the run as failed.
"""

import argparse
import sys
import time
from datetime import date
from pathlib import Path

import httpx

from queryrag.evaluation import (
    error_result,
    load_questions,
    render_markdown,
    results_to_json,
    score_question,
    summarize,
)


def describe_error(error: httpx.HTTPError) -> str:
    """Return a one-line description of an httpx error for console and report."""
    if isinstance(error, httpx.HTTPStatusError):
        # FastAPI puts the human-readable reason in "detail".
        try:
            detail = error.response.json().get("detail", "")
        except ValueError:
            detail = error.response.text[:200]
        return (
            f"HTTP {error.response.status_code} on {error.request.url.path}: {detail}"
        )

    return f"{type(error).__name__}: {error}"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--questions", default="eval/efta_faqs_questions.json")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--output-dir", default="eval/results")
    # A short pause between questions keeps us under free-tier rate limits.
    parser.add_argument("--pause-seconds", type=float, default=1.0)
    parser.add_argument(
        "--label",
        default="",
        help="Suffix for report filenames so runs don't overwrite each other, "
        "e.g. prompt-v3-run1",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    meta, questions = load_questions(Path(args.questions))
    filename = Path(meta["document"]).name
    results = []

    with httpx.Client(base_url=args.base_url, timeout=60) as client:
        # Fail fast with an actionable message instead of recording ten
        # identical connection errors when the server isn't running.
        try:
            client.get("/health").raise_for_status()
        except httpx.HTTPError as error:
            sys.exit(
                f"Cannot reach the API at {args.base_url} ({describe_error(error)}). "
                "Is uvicorn running?"
            )

        for question in questions:
            body = {"query": question.question, "limit": args.limit}
            started = time.perf_counter()

            try:
                search_payload = (
                    client.post("/search", json=body).raise_for_status().json()
                )

                # Latency measures /query only (retrieval + generation), which
                # is what an end user waits for.
                started = time.perf_counter()
                query_response = client.post("/query", json=body).raise_for_status()
                latency_ms = (time.perf_counter() - started) * 1000

                result = score_question(
                    question,
                    search_payload,
                    query_response.json(),
                    latency_ms,
                    filename,
                )
            except httpx.HTTPError as error:
                # Record and continue: one transient failure shouldn't discard
                # the results already collected for the other questions.
                latency_ms = (time.perf_counter() - started) * 1000
                result = error_result(question, describe_error(error), latency_ms)

            results.append(result)

            distance = (
                f"{result.top_distance:.3f}" if result.top_distance is not None else "–"
            )
            status = f"ERROR  {result.error}" if result.error else ""
            print(
                f"{result.id}  {result.type:<26} "
                f"distance={distance}  "
                f"correct_behaviour={result.abstention_correct}  "
                f"{latency_ms:.0f} ms  {status}"
            )
            time.sleep(args.pause_seconds)

    summary = summarize(results)
    # Run settings are written into the report so results are reproducible.
    settings = {
        "limit": args.limit,
        "base_url": args.base_url,
        "date": date.today(),
        "label": args.label or "none",
    }

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = f"{date.today()}-{meta['dataset']}"
    if args.label:
        stem = f"{stem}-{args.label}"
    (output_dir / f"{stem}.md").write_text(
        render_markdown(meta, results, summary, settings), encoding="utf-8"
    )
    (output_dir / f"{stem}.json").write_text(results_to_json(results), encoding="utf-8")

    print("\nSummary")
    for key, value in summary.items():
        print(f"  {key:<28} {value}")
    print(f"\nReport written to {output_dir / (stem + '.md')}")

    # Non-zero exit lets CI and shell scripts detect an incomplete run.
    if summary["errors"] != "0":
        print("Some questions failed with errors; see the report. Rerun to confirm.")
        sys.exit(1)


if __name__ == "__main__":
    main()
