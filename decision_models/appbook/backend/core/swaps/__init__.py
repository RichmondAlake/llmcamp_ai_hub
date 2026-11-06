"""The seven swaps, in the order of the notebooks: each module is one notebook's comparison, live.

A module has META (what today does, what the decision model asks, how the notebook judged it),
EXAMPLES (the notebook's "where it breaks" cases), `try_` (one input through today and every
chosen decision model), and a labelled set with its scorer.
"""
from __future__ import annotations

from backend.core import evidence
from backend.core.swaps import cache, chunking, consolidation, extraction, reranking, routing, tools

MODULES = [chunking, reranking, cache, routing, consolidation, extraction, tools]
#: Pages of docs/the-decision-on-decision-models.pdf for each swap: the technique, then the swap
#: (rendered to ../notebooks/img/reference/, the same figures the notebooks show).
FIGURES = {"chunking": (9, 26), "reranking": (10, 27), "cache": (11, 28, 29), "routing": (12, 30),
           "consolidation": (13, 31), "extraction": (14, 32), "tools": (15, 33)}


def figures(swap_id: str) -> list[dict]:
    from backend.config import NOTEBOOK_IMG_DIR

    out = []
    for n in FIGURES.get(swap_id, ()):
        found = sorted((NOTEBOOK_IMG_DIR / "reference").glob(f"p{n:02d}_*.png"))
        if found:
            out.append({"page": n, "src": f"/img/reference/{found[0].name}"})
    return out


BY_ID = {m.META["id"]: m for m in MODULES}


def items(module, session):
    return module.labelled_items(session) if module in (reranking, tools) else module.labelled_items()


def scorer(module, session):
    return module.scorer(session) if module is reranking else module.score


def describe(module) -> dict:
    meta = dict(module.META)
    meta["examples"] = module.EXAMPLES
    meta["figures"] = figures(meta["id"])
    meta["scorecard"] = evidence.scorecard(meta["notebook"])
    return meta


def catalog() -> list[dict]:
    return [describe(m) for m in MODULES]
