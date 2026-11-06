"""Tokenomics: latency, tokens and cost of every decision this session asked, per model and page."""
from __future__ import annotations

from fastapi import APIRouter

from backend.config import BACKENDS, TYPICAL_COLOR
from backend.core import session

router = APIRouter(prefix="/api", tags=["tokenomics"])


def _quantile(values: list[float], q: float):
    if not values:
        return None
    values = sorted(values)
    return values[min(len(values) - 1, int(q * (len(values) - 1) + 0.5))]


@router.get("/tokenomics")
def tokenomics():
    s = session.current()
    calls, groups = [], {}
    for entry in s.calls:
        for name, call in entry["calls"].items():
            if call.get("error") or call.get("ms") is None:
                continue
            count = call.get("count") or 1
            label = call.get("label") or BACKENDS.get(name, {}).get("label", name)
            row = {"n": entry["n"], "page": entry["page"], "model": label, "backend": name,
                   "kind": call.get("kind") or "decision", "count": count,
                   "ms": call["ms"], "ms_per_request": call["ms"] / count if call.get("kind") != "batch" else None,
                   "input_tokens": call.get("input_tokens") or 0, "usd": call.get("usd") or 0.0,
                   "color": BACKENDS.get(name, {}).get("color", TYPICAL_COLOR)}
            calls.append(row)
            g = groups.setdefault(label, {"model": label, "backend": name, "color": row["color"], "requests": 0,
                                          "ms": [], "input_tokens": 0, "usd": 0.0})
            g["requests"] += count
            if row["kind"] != "batch":
                g["ms"].append(row["ms"])
            g["input_tokens"] += row["input_tokens"]
            g["usd"] += row["usd"]
    summary = []
    for g in groups.values():
        summary.append({"model": g["model"], "backend": g["backend"], "color": g["color"], "requests": g["requests"],
                        "p50_ms": _quantile(g["ms"], 0.5), "p95_ms": _quantile(g["ms"], 0.95),
                        "input_tokens": g["input_tokens"], "usd": g["usd"],
                        "usd_per_1000": g["usd"] / g["requests"] * 1000 if g["requests"] else None,
                        "tokens_per_request": g["input_tokens"] / g["requests"] if g["requests"] else None})
    return {"session": s.id, "calls": calls, "summary": summary,
            "note": "Single decisions are timed one by one; label-set runs count every request and are left out of the latency quantiles."}
