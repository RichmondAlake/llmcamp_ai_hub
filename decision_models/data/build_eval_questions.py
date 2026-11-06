"""Build data/eval_questions.json: questions whose gold answers are exact substrings of the text.

The recipe from Chroma's chunking report: ask a chat model for question and excerpt pairs, keep only
excerpts that really occur in the text, drop near-duplicate questions by embedding similarity, and
check the rest by hand. Run from the decision_models folder:

    .venv/bin/python data/build_eval_questions.py --out data/eval_candidates.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import harness  # noqa: E402

PROMPT = """Below is one part of a support call transcript, about {topic}.

Write {count} questions a colleague might later ask that this part answers. For each one, copy the
shortest exact excerpt from the transcript that answers it, character for character, including any
speaker label only if it falls inside the excerpt. Use one excerpt, or two if the answer needs both.

Avoid yes/no questions, and do not repeat words from the excerpt where a paraphrase is natural.
Reply with JSON only: {{"questions": [{{"question": "...", "excerpts": ["..."]}}]}}

Transcript:
\"\"\"{part}\"\"\"
"""


def candidates(llm, text: str, topic: dict, count: int) -> list[dict]:
    part = text[topic["start"] : topic["end"]]
    reply = llm.generate_text(PROMPT.format(topic=topic["topic"].replace("_", " "), count=count, part=part))
    reply = reply.strip().removeprefix("```json").removeprefix("```").removesuffix("```")
    kept = []
    for row in json.loads(reply)["questions"]:
        excerpts = [e.strip() for e in row["excerpts"] if e.strip()]
        if excerpts and all(text.count(e) == 1 for e in excerpts):
            kept.append({"question": row["question"].strip(), "excerpts": excerpts, "topic": topic["topic"]})
    return kept


def drop_near_duplicates(rows: list[dict], threshold: float) -> list[dict]:
    from memorizz.embeddings import get_embedding

    vectors = np.array([get_embedding(row["question"]) for row in rows], dtype=float)
    vectors /= np.linalg.norm(vectors, axis=1, keepdims=True)
    kept: list[int] = []
    for i in range(len(rows)):
        if all(float(vectors[i] @ vectors[j]) < threshold for j in kept):
            kept.append(i)
    return [rows[i] for i in kept]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="data/eval_candidates.json")
    parser.add_argument("--per-topic", type=int, default=9)
    parser.add_argument("--threshold", type=float, default=0.85)
    args = parser.parse_args()

    harness.load_env()
    from memorizz.llms.llm_factory import create_llm_provider

    llm = create_llm_provider({"provider": "openai", "model": harness.CHAT_MODEL})
    text = (harness.DATA / "demo_text.md").read_text()
    topics = json.loads((harness.DATA / "demo_text.json").read_text())["topics"]

    rows = [row for topic in topics for row in candidates(llm, text, topic, args.per_topic)]
    print(f"{len(rows)} candidates with exact excerpts")
    rows = drop_near_duplicates(rows, args.threshold)
    print(f"{len(rows)} after dropping near-duplicates")
    Path(args.out).write_text(json.dumps(rows, indent=2))


if __name__ == "__main__":
    main()
