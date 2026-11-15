"""Run the QueryRAG evaluation set against a running API.

Usage (from the project root, with the server running):
    uv run --project backend python scripts/run_eval.py
"""

import argparse
import time
from datetime import date
from pathlib import Path

import httpx

from queryrag.evaluation import (
    load_questions,
    render_markdown,
    results_to_json,
    score_question,
    summarize,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--questions", default="eval/efta_faqs_questions.json")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--output-dir", default="eval/results")
    parser.add_argument("--pause-seconds", type=float, default=1.0)
    args = parser.parse_args()

    meta, questions = load_questions(Path(args.questions))
    filename = Path(meta["document"]).name
    results = []

    with httpx.Client(base_url=args.base_url, timeout=60) as client:
        for question in questions:
            body = {"query": question.question, "limit": args.limit}

            search_payload = client.post("/search", json=body).raise_for_status().json()

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
            results.append(result)

            distance = (
                f"{result.top_distance:.3f}" if result.top_distance is not None else "–"
            )
            print(
                f"{result.id}  {result.type:<26} "
                f"distance={distance}  "
                f"correct_behaviour={result.abstention_correct}  "
                f"{latency_ms:.0f} ms"
            )
            time.sleep(args.pause_seconds)

    summary = summarize(results)
    settings = {"limit": args.limit, "base_url": args.base_url, "date": date.today()}

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = f"{date.today()}-{meta['dataset']}"
    (output_dir / f"{stem}.md").write_text(
        render_markdown(meta, results, summary, settings), encoding="utf-8"
    )
    (output_dir / f"{stem}.json").write_text(results_to_json(results), encoding="utf-8")

    print("\nSummary")
    for key, value in summary.items():
        print(f"  {key:<28} {value}")
    print(f"\nReport written to {output_dir / (stem + '.md')}")


if __name__ == "__main__":
    main()
