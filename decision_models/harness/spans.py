"""Character spans: where chunks sit in the text, and how well they cover the gold answers.

The retrieval metrics follow the span definitions in Chroma's "Evaluating Chunking Strategies for
Retrieval" (Smith and Troynikov, 2024):

    recall    = covered gold characters / gold characters
    precision = covered gold characters / retrieved characters
    IoU       = covered gold characters / (retrieved characters + gold characters not retrieved)

Retrieved characters are counted with repetition, so overlap between chunks counts against
precision and IoU. That is what penalises a fixed window with overlap.
"""

from __future__ import annotations

import re
from bisect import bisect_right
from typing import Iterable, Sequence

SENTENCE_END = re.compile(r"(?<=[.?!])\s+")

Span = tuple[int, int]


def split_sentences(text: str) -> list[str]:
    """Split on the same regex LangChain's SemanticChunker uses, so every method shares one index."""
    return [part for part in SENTENCE_END.split(text.strip()) if part]


def sentence_starts(text: str, sentences: Sequence[str] | None = None) -> list[int]:
    """The character offset where each sentence starts."""
    sentences = split_sentences(text) if sentences is None else sentences
    starts, cursor = [], 0
    for sentence in sentences:
        cursor = text.index(sentence, cursor)
        starts.append(cursor)
        cursor += len(sentence)
    return starts


def locate(text: str, chunk: str, cursor: int = 0) -> Span:
    """Find a chunk's span. Whitespace may differ: some chunkers rejoin sentences with spaces."""
    pattern = r"\s+".join(re.escape(word) for word in chunk.split())
    found = re.compile(pattern).search(text, cursor) or re.compile(pattern).search(text)
    if found is None:
        raise ValueError(f"Chunk not found in the text: {chunk[:60]!r}")
    return found.start(), found.end()


def with_offsets(text: str, chunks: Iterable[str]) -> list[dict]:
    """Chunks as {"text", "start", "end"}, the shape results/chunks_*.json stores."""
    rows, cursor = [], 0
    for chunk in chunks:
        if not chunk.strip():
            continue
        start, end = locate(text, chunk, cursor)
        rows.append({"text": chunk, "start": start, "end": end})
        cursor = start + 1  # overlapping chunks may start inside the previous one
    return rows


def _merge(spans: Iterable[Span]) -> list[Span]:
    merged: list[list[int]] = []
    for start, end in sorted(spans):
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return [(start, end) for start, end in merged]


def _overlap(left: Sequence[Span], right: Sequence[Span]) -> int:
    return sum(max(0, min(a_end, b_end) - max(a_start, b_start))
               for a_start, a_end in left for b_start, b_end in right)


def retrieval_scores(retrieved: Sequence[Span], gold: Sequence[Span]) -> dict[str, float]:
    """Span recall, precision and IoU for one question."""
    gold_merged = _merge(gold)
    gold_total = sum(end - start for start, end in gold_merged)
    retrieved_total = sum(end - start for start, end in retrieved)
    covered = _overlap(_merge(retrieved), gold_merged)
    return {
        "recall": covered / gold_total if gold_total else 0.0,
        "precision": covered / retrieved_total if retrieved_total else 0.0,
        "iou": covered / (retrieved_total + gold_total - covered) if retrieved_total + gold_total else 0.0,
    }


def boundary_scores(predicted: Iterable[int], gold: Iterable[int], starts: Sequence[int],
                    tolerance: int = 1) -> dict[str, float]:
    """Boundary precision and recall with a tolerance in sentences, one gold matched at most once.

    `predicted` and `gold` are character offsets. Offset 0 is the start of the text, not a cut, so
    it is dropped from both sides.
    """

    def index(offset: int) -> int:
        return max(0, bisect_right(starts, offset) - 1)

    predicted_i = sorted({index(offset) for offset in predicted if offset > 0})
    gold_i = sorted({index(offset) for offset in gold if offset > 0})
    unmatched = set(gold_i)
    true_positive = 0
    for cut in predicted_i:
        near = [g for g in unmatched if abs(g - cut) <= tolerance]
        if near:
            unmatched.discard(min(near, key=lambda g: abs(g - cut)))
            true_positive += 1
    precision = true_positive / len(predicted_i) if predicted_i else 0.0
    recall = true_positive / len(gold_i) if gold_i else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"precision": precision, "recall": recall, "f1": f1, "cuts": len(predicted_i),
            "true_positive": true_positive}
