"""Swap 5 · consolidation and dedup (notebook 05): cosine above 0.95 vs a five-way choice."""
from __future__ import annotations

import harness
import numpy as np
from harness import questions as Q

from backend.core.swaps import common

META = {
    "id": "consolidation", "today_short": "cosine > 0.95", "n": 5, "title": "Consolidation and dedup", "stage": "Retain · Refine",
    "notebook": "05_consolidation",
    "subtitle": "Cosine above 0.95 vs a five-way choice",
    "when": "At write time and in background consolidation, never on a user's turn. Decisions 6, 7, 8 and 10.",
    "today": "Find the most similar stored memory; above 0.95 cosine the new one is a duplicate (skip it), below it is inserted.",
    "model": "One Choice: same → skip, refines → update, contradicts → supersede (mark the old one, keep it), complements → link, unrelated → insert.",
    "judge": "50 hand-labelled pairs, ten per relation: the right action, and contradictions caught.",
    "input": "pair", "question": Q.DEDUP,
    "takeaways": [
        "A contradiction is as similar as a duplicate. A cut-off cannot tell them apart, at any setting.",
        "Ask how the two memories relate, and let the relation pick the action.",
        "Measured: 0.88 of actions right against 0.20, and every contradiction caught.",
        "Supersede marks the old memory instead of deleting it: forget, don't delete.",
    ],
}

DATA = harness.labels("dedup")
ACTION = DATA["actions"]
PAIRS = DATA["pairs"]
LABELS = {(p["stored"], p["new"]): p["relation"] for p in PAIRS}


def _pick(relation, contains):
    return next(p for p in PAIRS if p["relation"] == relation and contains in p["stored"])


EXAMPLES = [{"label": f"{p['stored']} → {p['new']}", "input": {"stored": p["stored"], "new": p["new"]}}
            for p in (_pick("refines", "Python"), _pick("contradicts", "London"), _pick("same", "manager"),
                      _pick("complements", "Lisbon"))]


def try_(session, pair: dict, backends: list[str]) -> dict:
    stored, new = pair["stored"].strip(), pair["new"].strip()
    relation = LABELS.get((stored, new))
    right_action = ACTION[relation] if relation else None
    methods = []

    def today():
        v = common.embed([stored, new])
        sim = float(v[0] @ v[1])
        action = "skip" if sim > 0.95 else "insert"
        return {"answer": action, "right": (action == right_action) if right_action else None,
                "lines": [{"text": f"cosine similarity {sim:.3f} ({'above' if sim > 0.95 else 'below'} 0.95)", "ok": None}],
                "usd": common.embed_usd([new])}

    if common.openai_ready():
        methods.append(common.today("Cosine above 0.95", today))
    state = {"stored_memory": stored, "new_memory": new}
    for name, rec in common.ask_each(backends, state, {"relation": Q.DEDUP}).items():
        answer = (rec.get("answers") or {}).get("relation", {})
        choice = answer.get("choice")
        action = ACTION.get(choice, "no answer")
        lines = [{"text": f"{k}: {v:.2f}", "ok": None} for k, v in sorted((answer.get("probabilities") or {}).items(), key=lambda kv: -kv[1])[:3]]
        methods.append(common.model_record(name, rec, f"{choice} → {action}", (action == right_action) if right_action else None, lines))
    common.log(session, "consolidation", methods, f"{stored} | {new}")
    truth = f"Labelled: {relation} → {right_action}" if relation else None
    return {"input": pair, "methods": methods, "truth": truth}


def labelled_items():
    return [({"stored_memory": p["stored"], "new_memory": p["new"]}, {"relation": Q.DEDUP}) for p in PAIRS]


def score(answers: list) -> dict:
    chosen = [a["relation"]["choice"] if a else None for a in answers]
    right = [ACTION.get(c) == ACTION[p["relation"]] for c, p in zip(chosen, PAIRS)]
    contra = [ok for ok, p in zip(right, PAIRS) if p["relation"] == "contradicts"]
    return {"measure": "right action", "score": float(np.mean(right)),
            "detail": f"{sum(right)} of {len(right)} actions right, {sum(contra)} of {len(contra)} contradictions caught"}


def dots() -> dict:
    """Cosine similarity of every labelled pair, by relation (notebook 05's chart)."""
    v_old, v_new = common.embed([p["stored"] for p in PAIRS]), common.embed([p["new"] for p in PAIRS])
    sims = np.sum(v_old * v_new, axis=1)
    return {"groups": {r: [float(s) for s, p in zip(sims, PAIRS) if p["relation"] == r] for r in DATA["relations"]},
            "line": 0.95}
