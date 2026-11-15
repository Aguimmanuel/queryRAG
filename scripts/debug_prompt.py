"""Show exactly what Gemini sees and says for one eval question.

The /query endpoint hides the model's raw reply when it abstains
(it swaps in the standard insufficient-evidence message). This script
rebuilds the same prompt and prints the raw reply, so we can see WHY
the model refused.

Usage (from ~/queryRAG, with the server running):
    uv run --project backend --env-file "$HOME/queryRAG/.env" \
        python scripts/debug_prompt.py q07
"""

import argparse
import json
from pathlib import Path

import httpx

from queryrag.config import get_settings
from queryrag.generation import (
    Evidence,
    build_grounded_prompt,
    filter_relevant_evidence,
    is_abstention_reply,
)
from queryrag.providers.gemini import create_gemini_generator

QUESTIONS_FILE = Path("eval/efta_faqs_questions.json")


def load_question(question_id: str) -> str:
    data = json.loads(QUESTIONS_FILE.read_text(encoding="utf-8"))

    for item in data["questions"]:
        if item["id"] == question_id:
            return item["question"]

    raise SystemExit(f"Question {question_id} not found in {QUESTIONS_FILE}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("question_id", help="e.g. q07")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--show-prompt", action="store_true")
    args = parser.parse_args()

    settings = get_settings()
    question = load_question(args.question_id)

    # Same retrieval the /query endpoint uses, via the /search endpoint.
    response = httpx.post(
        f"{args.base_url}/search",
        json={"query": question, "limit": args.limit},
        timeout=60,
    ).raise_for_status()

    evidence = [
        Evidence(
            document_id=item["document_id"],
            filename=item["filename"],
            page_number=item["page_number"],
            chunk_index=item["chunk_index"],
            text=item["text"],
            distance=item["distance"],
        )
        for item in response.json()["results"]
    ]
    kept = filter_relevant_evidence(evidence, settings.max_evidence_distance)

    print(f"Question: {question}\n")
    print(f"Evidence kept (distance <= {settings.max_evidence_distance}):")
    for item in kept:
        print(
            f"  page {item.page_number:>2}  chunk {item.chunk_index}  distance={item.distance:.3f}"
        )

    prompt = build_grounded_prompt(question, kept)

    if args.show_prompt:
        print("\n===== PROMPT SENT TO GEMINI =====")
        print(prompt)
        print("===== END PROMPT =====")

    reply = create_gemini_generator().generate(prompt)

    print("\n===== RAW GEMINI REPLY =====")
    print(reply)
    print("===== END REPLY =====")
    print(f"\nCounted as abstention: {is_abstention_reply(reply)}")


if __name__ == "__main__":
    main()
