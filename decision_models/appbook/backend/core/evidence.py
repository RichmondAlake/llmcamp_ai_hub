"""What the notebooks measured, read from `results/*.jsonl`. Nothing here calls a model.

Each swap notebook (01 to 07) ends with a scorecard and records it as one `summary` row. Notebook 09
records one `metric` row per swap and decision model.
"""
from __future__ import annotations

from functools import lru_cache

import harness
import pandas as pd


@lru_cache(maxsize=16)
def scorecard(notebook: str) -> dict | None:
    """The swap notebook's scorecard, or None when it has not been run."""
    path = harness.RESULTS / f"{notebook}.jsonl"
    if not path.exists():
        return None
    log = pd.read_json(path, lines=True)
    if "kind" not in log or not (log["kind"] == "summary").any():
        return None
    row = log[log["kind"] == "summary"].iloc[-1].to_dict()
    keep = ("swap", "measure", "today_label", "model_label", "today", "model", "verdict", "low", "high", "n", "also", "extra")
    return {k: row.get(k) for k in keep} | {"source": f"results/{notebook}.jsonl"}


def scoreboard() -> list[dict]:
    from backend.core.swaps import MODULES

    return [{"id": m.META["id"], "n": m.META["n"], "title": m.META["title"], "card": scorecard(m.META["notebook"])}
            for m in MODULES]


@lru_cache(maxsize=1)
def providers() -> dict:
    """Notebook 09: every swap's decision asked of d1, Jev and OpenAI Decisions."""
    path = harness.RESULTS / "09_decision_model_providers.jsonl"
    if not path.exists():
        return {"rows": [], "costs": [], "source": "notebook 09 has not been run"}
    log = pd.read_json(path, lines=True)
    metrics = log[log["kind"] == "metric"]
    rows = [{"swap": r["swap"], "model": r["label"], "measure": r["name"], "score": float(r["value"])}
            for _, r in metrics.iterrows()]
    costs = log[log["kind"] == "cost"]
    by_model: dict[str, dict] = {}
    for _, r in costs.iterrows():
        model = str(r["label"]).split(":", 1)[0]
        entry = by_model.setdefault(model, {"model": model, "usd": 0.0, "requests": 0, "input_tokens": 0})
        entry["usd"] += float(r["usd"])
        entry["requests"] += int(r.get("count") or 0)
        entry["input_tokens"] += int(r["input_tokens"])
    return {"rows": rows, "costs": list(by_model.values()), "source": "results/09_decision_model_providers.jsonl"}


def clear() -> None:
    scorecard.cache_clear()
    providers.cache_clear()
