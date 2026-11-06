"""The reference architecture: the twenty decision points of the memory loop, and the seven swaps.

The rows are notebook 00's inventory (`harness.decision_points`). A built point links to the swap
page that asks it live and carries that swap notebook's scorecard. The semantic cache is the one
swap that is not among the twenty: it sits in front of recall, on the read path.
"""
from __future__ import annotations

from harness.decision_points import DECISION_POINTS, R_ORDER

from backend.core import evidence

STAGES = {
    "Retain": "Writing: what becomes a memory, in which form, and whether it repeats or contradicts what is stored.",
    "Refine": "Upkeep: what stays true, what merges, and what was worth keeping.",
    "Recall": "Reading: whether to search, where, and which results reach the prompt.",
    "Reuse": "Acting: which tool or skill runs, and whether a call should run as written.",
}

#: decision point → swap page
PAGES = {1: "chunking", 2: "extraction", 3: "extraction", 6: "consolidation", 7: "consolidation",
         8: "consolidation", 10: "consolidation", 13: "routing", 14: "routing", 16: "reranking", 19: "tools"}

#: the decision each point asks, and the primitive's question type
PRIMITIVE = {1: "noul", 2: "noul", 3: "choice", 4: "choice", 5: "noul", 6: "choice", 7: "choice", 8: "choice",
             9: "noul", 10: "choice", 11: "noul", 12: "noul", 13: "noul", 14: "noul", 15: "noul",
             16: "noul", 17: "noul", 18: "noul", 19: "choice", 20: "noul"}


def reference() -> dict:
    from backend.core.swaps import BY_ID

    cards = {sid: evidence.scorecard(module.META["notebook"]) for sid, module in BY_ID.items()}
    points = []
    for p in DECISION_POINTS:
        page = PAGES.get(p["n"])
        point = {**p, "type": PRIMITIVE[p["n"]], "page": page, "status": "built" if page else "listed"}
        if page:
            meta = BY_ID[page].META
            point.update(swap=meta["n"], swap_title=meta["title"], card=cards[page])
        points.append(point)
    cache = BY_ID["cache"].META
    return {"stages": [{"name": r, "description": STAGES[r]} for r in R_ORDER], "points": points,
            "built": sum(1 for p in points if p["status"] == "built"),
            "extra": {"page": "cache", "swap": cache["n"], "swap_title": cache["title"], "card": cards["cache"],
                      "question": "Can this cached answer serve this query?", "where": "read path, before recall"},
            "swaps": [{"id": sid, "n": m.META["n"], "title": m.META["title"], "verdict": (cards[sid] or {}).get("verdict")}
                      for sid, m in BY_ID.items()]}
