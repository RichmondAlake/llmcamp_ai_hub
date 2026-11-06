"""Swap 3 · semantic cache (notebook 03): a cosine threshold vs "can this cached answer serve this query?"."""
from __future__ import annotations

import re

import harness
import numpy as np
from harness import questions as Q

from backend.core.swaps import common

META = {
    "id": "cache", "today_short": "cosine ≥ 0.9", "n": 3, "title": "Semantic cache", "stage": "Recall", "notebook": "03_semantic_cache",
    "subtitle": 'A cosine threshold vs "can this cached answer serve this query?"',
    "when": "Every turn, on the hot path, before retrieval and the LLM.",
    "today": "Embed the query, find the closest cached question, and return its stored answer when cosine similarity is at least 0.9.",
    "model": 'An exact match is still free; otherwise take the three closest cached entries and ask "can this cached answer correctly answer the new question?". Hit only on a yes.',
    "judge": "48 labelled lookups: right decisions, paraphrases served, wrong answers served, milliseconds per lookup and cost.",
    "input": "query", "question": Q.CACHE_SERVES,
    "takeaways": [
        "A cosine threshold cannot tell a paraphrase from a near miss, so it trades hit rate for wrong answers.",
        "Ask about the cached answer: can it serve this question, as asked?",
        "Measured: 20 of 20 paraphrases served instead of 2, with fewer wrong answers.",
        "Every lookup now pays for a decision. Keep an exact-match tier in front and check the hit rate clears the break-even.",
    ],
}

DATA = harness.labels("cache")
CACHED = DATA["cached"]
BY_ID = {c["id"]: c for c in CACHED}
LABELS = {q["query"]: q for q in DATA["queries"]}
EXAMPLES = [{"label": q, "input": q} for q in (
    "What's the weather in London tomorrow?", "How do I cancel my subscription?", "What was revenue for Q3?",
    "What was revenue for Q2 last year?", "Can you deliver to Toronto?", "Is it raining in London right now?")]


def _normalise(text: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", text.lower()).strip()


EXACT = {_normalise(c["question"]): c["id"] for c in CACHED}


def _closest(query: str, k: int):
    sims = common.embed([c["question"] for c in CACHED]) @ common.embed([query])[0]
    return [(CACHED[i]["id"], float(sims[i])) for i in np.argsort(-sims)[:k]]


def _verdict(query: str, served: str | None):
    label = LABELS.get(query)
    if not label:
        return None
    return served == label["serves"]


def _lines(served, similarity=None, p=None):
    if served is None:
        return [{"text": "miss: the agent runs and the answer is stored", "ok": None}]
    entry = BY_ID[served]
    extra = f" (similarity {similarity:.3f})" if similarity is not None else (f" (P = {p:.2f})" if p is not None else "")
    return [{"text": f"cached question: {entry['question']}{extra}", "ok": None},
            {"text": f"serves: {entry['answer']}", "ok": None}]


def try_(session, query: str, backends: list[str]) -> dict:
    methods = []

    def cosine():
        entry, sim = _closest(query, 1)[0]
        served = entry if sim >= 0.9 else None
        lines = _lines(served, sim) if served else [{"text": f"closest: {BY_ID[entry]['question']} (similarity {sim:.3f}, below 0.9)", "ok": None},
                                                    *_lines(None)]
        return {"answer": "hit" if served else "miss", "right": _verdict(query, served), "lines": lines,
                "usd": common.embed_usd([query])}

    if common.openai_ready():
        methods.append(common.today("Cosine at least 0.9", cosine))
    exact = EXACT.get(_normalise(query))
    candidates = [exact] if exact else [c for c, _ in _closest(query, 3)]
    items = [({"new_question": query, "cached_answer": BY_ID[c]["answer"]}, {"serves": Q.CACHE_SERVES}) for c in candidates]
    for name, rec in common.many_each(backends, items).items():
        scored = [(a["serves"]["noul"] if a else 0.0, c) for a, c in zip(rec["answers"], candidates)]
        p, best = max(scored)
        served = best if p >= 0.5 else None
        lines = [{"text": f"P(answer serves) = {pp:.2f} for: {BY_ID[c]['question']}", "ok": None} for pp, c in scored]
        lines += _lines(served) if served else _lines(None)
        if exact:
            lines.insert(0, {"text": "exact match: in production this tier answers with no model call", "ok": None})
        methods.append(common.model_record(name, rec, "hit" if served else "miss", _verdict(query, served), lines))
    common.log(session, "cache", methods, query)
    label = LABELS.get(query)
    truth = None
    if label:
        truth = f"The right answer: {'serve ' + repr(BY_ID[label['serves']]['question']) if label['serves'] else 'miss, no stored answer serves this'} ({label['kind']})"
    return {"input": query, "methods": methods, "truth": truth}


def labelled_items():
    items = []
    for q in DATA["queries"]:
        for c, _ in _closest(q["query"], 3):
            items.append(({"new_question": q["query"], "cached_answer": BY_ID[c]["answer"]}, {"serves": Q.CACHE_SERVES}))
    return items


def score(answers: list) -> dict:
    right, wrong_served, at = [], 0, 0
    for q in DATA["queries"]:
        cands = [c for c, _ in _closest(q["query"], 3)]
        p, best = max((a["serves"]["noul"] if a else 0.0, c) for a, c in zip(answers[at:at + 3], cands))
        at += 3
        served = best if p >= 0.5 else None
        right.append(served == q["serves"])
        wrong_served += served is not None and served != q["serves"]
    return {"measure": "right decisions", "score": float(np.mean(right)),
            "detail": f"{sum(right)} of {len(right)} lookups right, {wrong_served} wrong answers served"}


def trap() -> dict:
    """The threshold sweep from notebook 03, computed from embeddings (no decision model)."""
    nearest = {q["query"]: _closest(q["query"], 1)[0] for q in DATA["queries"]}
    para = [q for q in DATA["queries"] if q["kind"] == "paraphrase"]
    unservable = [q for q in DATA["queries"] if q["serves"] is None]
    thresholds = [round(t, 3) for t in np.arange(0.5, 1.0, 0.025)]
    served = [float(np.mean([nearest[q["query"]][1] >= t and nearest[q["query"]][0] == q["serves"] for q in para])) for t in thresholds]
    wrong = [float(np.mean([nearest[q["query"]][1] >= t for q in unservable])) for t in thresholds]
    return {"thresholds": thresholds, "paraphrases_served": served, "wrong_answers_served": wrong,
            "paraphrases": len(para), "unservable": len(unservable)}
