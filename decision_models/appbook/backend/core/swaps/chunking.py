"""Swap 1 · semantic chunking (notebook 01): a percentile cut vs "does a new topic start here?"."""
from __future__ import annotations

from bisect import bisect_right

import harness
import numpy as np
from harness import questions as Q
from harness.spans import boundary_scores, sentence_starts, split_sentences, with_offsets

from backend.core.swaps import common

META = {
    "id": "chunking", "today_short": "the percentile chunker", "n": 1, "title": "Semantic chunking", "stage": "Retain", "notebook": "01_semantic_chunking",
    "subtitle": 'A similarity drop vs "does a new topic start here?"',
    "when": "Once per document, at ingestion (write time). Decision 1.",
    "today": "Embed each sentence, compare it with the next, and cut where the similarity drops below the 95th-percentile line (LangChain's SemanticChunker).",
    "model": 'Ask "does a new topic, request or event start here?" at every gap between sentences, and cut where P ≥ 0.5.',
    "judge": "On a transcript with eight known topics and 40 questions: topic changes found, retrieval hit rate, and how much of a returned chunk is the answer.",
    "input": "page", "question": Q.CHUNK_BOUNDARY,
    "notes": [{"title": "What a gap is", "text": [
        "A gap is the point between the end of one sentence and the start of the next. A chunker never cuts inside a sentence, so the gaps are the only places it can cut, and chunking is deciding, gap by gap, whether to cut there. A text of n sentences has n − 1 gaps.",
        "Example: “Priya prefers Python. | She uses it for every script. || The migration deadline is Friday. | Marcus owns the cutover plan.” Four sentences, three gaps. Gaps 1 and 3 are inside a topic; gap 2 is where a new topic starts, so one cut there gives two chunks.",
        "Today’s chunker measures how similar the sentences either side of each gap are, and cuts at the lowest similarities in the document. The decision model is asked at every gap whether a new topic starts there, and cuts where P is 0.5 or more. The table under the answers shows both, gap by gap."]}],
    "takeaways": [
        "A percentile cut answers \"which gaps are most unusual here?\". Sections that share their words are never unusual, so they get merged.",
        "A decision model is asked \"does a new topic start here?\" directly, and its probability means the same thing on the next document.",
        "Measured: the same hit rate, about twice the utilisation, and more of the real topic changes found.",
        "Slower and a little dearer, but chunking happens once per document, at write time.",
    ],
}

PAGE = """## Short-term memory
Short-term memory holds what an agent needs within one session. It keeps the recent turns of the conversation and the state of the task in progress. It lives in the context window and in a session store, and it is summarised or cleared when the session ends.

## Long-term memory
Long-term memory keeps what an agent learns across sessions. It holds facts about the user, past conversations and procedures that worked. It lives in a database, it is searched on every turn, and it survives restarts.

## Saving a memory
The function below saves one memory with its embedding.
```python
def remember(store, text):
    vector = embed(text)
    store.insert(text=text, vector=vector)
```
It embeds the text once and stores the text and the vector together. Later searches can then find the memory by meaning.
"""
PAGE_SECTION_GAPS = {2, 5}
EXAMPLES = [{"label": "Three sections, two of them about memory", "input": PAGE}]


def _semantic(text: str, percentile: int = 95) -> list[str]:
    from langchain_experimental.text_splitter import SemanticChunker
    from langchain_openai import OpenAIEmbeddings

    chunker = SemanticChunker(OpenAIEmbeddings(model=harness.EMBEDDING_MODEL),
                              breakpoint_threshold_type="percentile", breakpoint_threshold_amount=percentile)
    return [c for c in chunker.split_text(text) if c.strip()]


def _similarity(sentences: list[str]) -> list[float]:
    windows = [" ".join(sentences[max(0, i - 1): i + 2]) for i in range(len(sentences))]
    v = common.embed(windows)
    return [float(x) for x in np.sum(v[:-1] * v[1:], axis=1)]


def try_(session, text: str, backends: list[str]) -> dict:
    sentences = split_sentences(text)
    if len(sentences) < 3:
        raise ValueError("Give at least three sentences.")
    is_page = text.strip() == PAGE.strip()
    real = PAGE_SECTION_GAPS if is_page else None
    methods = []
    similarity: list[float] = []

    def run_today():
        chunks = _semantic(text)
        similarity.extend(_similarity(sentences))
        starts = sentence_starts(text, sentences)
        cut_gaps = sorted({bisect_right(starts, row["start"]) - 2 for row in with_offsets(text, chunks)[1:]})
        right = None    # one page is a demonstration: each cut is marked against the real section changes
        lines = [{"text": f"cut after sentence {i}" + (" · real section change" if real and i in real else ""),
                  "ok": (i in real) if real else None} for i in cut_gaps] or [{"text": "no cuts: one chunk", "ok": False if real else None}]
        return {"answer": f"{len(chunks)} chunk{'s' if len(chunks) != 1 else ''}", "right": right, "lines": lines,
                "usd": common.embed_usd(sentences)}

    if common.openai_ready():
        methods.append(common.today("SemanticChunker, 95th percentile", run_today))
    items = [(Q.boundary_state(sentences, i), {"boundary": Q.CHUNK_BOUNDARY}) for i in range(len(sentences) - 1)]
    probs = {}
    for name, rec in common.many_each(backends, items).items():
        p = [a["boundary"]["noul"] if a else None for a in rec["answers"]]
        probs[name] = p
        cuts = [i for i, v in enumerate(p) if v is not None and v >= 0.5]
        edges = [0] + [i + 1 for i in cuts] + [len(sentences)]
        chunks = [" ".join(sentences[a:b]) for a, b in zip(edges, edges[1:])]
        right = None
        lines = [{"text": f"cut after sentence {i}" + (" · real section change" if real and i in real else ""),
                  "ok": (i in real) if real else None} for i in cuts] or [{"text": "no cuts", "ok": None}]
        methods.append(common.model_record(name, rec, f"{len(chunks)} chunks", right, lines))
    gaps = [{"i": i, "before": sentences[i][-60:].replace("\n", " "), "after": sentences[i + 1][:60].replace("\n", " "),
             "real": (i in real) if real else None, "similarity": similarity[i] if similarity else None,
             "p": {name: probs[name][i] for name in probs}} for i in range(len(sentences) - 1)]
    common.log(session, "chunking", methods, f"{len(sentences)} sentences")
    return {"input": text, "methods": methods, "gaps": gaps}


def labelled_items():
    text, _ = harness.demo()
    sentences = split_sentences(text)
    return [(Q.boundary_state(sentences, i), {"boundary": Q.CHUNK_BOUNDARY}) for i in range(len(sentences) - 1)]


def score(answers: list) -> dict:
    text, gold = harness.demo()
    sentences = split_sentences(text)
    starts = sentence_starts(text, sentences)
    real = [t["start"] for t in gold["topics"][1:]]
    p = [a["boundary"]["noul"] if a else 0.0 for a in answers]
    cuts = [starts[i + 1] for i, v in enumerate(p) if v >= 0.5]
    found = boundary_scores(cuts, real, starts, tolerance=1)
    today_cuts = None
    if common.openai_ready():
        try:
            today_cuts = [row["start"] for row in with_offsets(text, _semantic(text))][1:]
        except Exception:  # noqa: BLE001 — the map still shows the decision model
            today_cuts = None
    return {"measure": "boundary F1", "score": found["f1"],
            "detail": f"{found['true_positive']} of {len(real)} real topic changes found, {found['cuts'] - found['true_positive']} extra cuts",
            "map": {"length": len(text), "topics": [[t["start"], t["topic"].replace("_", " ")] for t in gold["topics"]],
                    "cuts": cuts, "today_cuts": today_cuts}}
