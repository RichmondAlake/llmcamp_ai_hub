"""The Data Explorer: a read-only, allowlisted view of what the notebooks and this app stored.

It accepts no query language. A table is one of the names below; rows are paged and capped, long
text is cut to 300 characters, and vectors are never sent.
"""
from __future__ import annotations

import json
from pathlib import Path

import harness

from backend.config import BACKENDS

MAX_LIMIT = 100
MAX_COLUMNS = 14
MEMORY_TYPES = ["knowledge_base", "toolbox", "conversation_memory", "entity_memory"]
_SKIP = {"embedding", "embeddings", "vector", "vectors"}


def _labels(name: str, key: str):
    return lambda: harness.labels(name)[key]


TABLES: dict[str, dict] = {
    "session_decisions": {"group": "This session", "role": "Every decision this lab session asked"},
    "labels_cache": {"group": "Labels", "role": "48 lookups against 16 cached answers (swap 3)",
                     "rows": _labels("cache", "queries")},
    "labels_memory_routing": {"group": "Labels", "role": "58 turns and the memory types each needs (swap 4)",
                              "rows": _labels("memory_routing", "turns")},
    "labels_dedup": {"group": "Labels", "role": "50 memory pairs and how they relate (swap 5)",
                     "rows": _labels("dedup", "pairs")},
    "labels_extraction": {"group": "Labels", "role": "60 turns: worth remembering, and the type (swap 6)",
                          "rows": _labels("extraction", "turns")},
    "labels_tools": {"group": "Labels", "role": "75 turns: the tool that should run, or none (swap 7)",
                     "rows": _labels("tools", "turns")},
    "eval_questions": {"group": "Labels", "role": "40 questions with gold excerpts (swaps 1 and 2)",
                       "rows": harness.eval_questions},
}
for path in sorted(harness.RESULTS.glob("[0-9][0-9]_*.jsonl")):
    TABLES[f"results_{path.stem}"] = {"group": "Notebook results", "role": f"rows notebook {path.stem[:2]} recorded",
                                      "path": path}
for kind in MEMORY_TYPES:
    TABLES[f"memorizz_{kind}"] = {"group": "MemoRizz store", "role": f"MemoRizz {kind} records", "memory_type": kind}


def _clean(value):
    if isinstance(value, str):
        return value if len(value) <= 300 else value[:300] + "…"
    if isinstance(value, (list, dict)):
        if isinstance(value, list) and len(value) > 32 and all(isinstance(v, (int, float)) for v in value[:32]):
            return f"[{len(value)} numbers]"
        text = json.dumps(value, default=str)
        return text if len(text) <= 300 else text[:300] + "…"
    return value


def _store_rows(kind: str, scope: str, session) -> list[dict]:
    roots = [session.store_path] if scope == "session" else sorted(p for p in harness.STORE.iterdir() if p.is_dir())
    rows = []
    for root in roots:
        folder = root / kind
        if not folder.is_dir():
            continue
        for file in sorted(folder.glob("*.json")):
            try:
                record = json.loads(file.read_text())
            except (OSError, json.JSONDecodeError):
                continue
            rows.append({"store": root.name, **{k: v for k, v in record.items() if k not in _SKIP}})
    return rows


def _session_rows(session) -> list[dict]:
    rows = []
    for entry in session.calls:
        for name, call in entry["calls"].items():
            answer = call.get("answers")
            rows.append({"n": entry["n"], "at": entry["at"], "page": entry["page"],
                         "model": call.get("label") or BACKENDS.get(name, {}).get("label", name),
                         "kind": call.get("kind") or "decision", "count": call.get("count") or 1,
                         "ms": round(call["ms"], 1) if call.get("ms") is not None else None,
                         "input_tokens": call.get("input_tokens"), "usd": call.get("usd"),
                         "input": entry["summary"], "answers": answer, "error": call.get("error")})
    return list(reversed(rows))


def rows_of(name: str, session, scope: str = "session") -> list[dict]:
    spec = TABLES[name]
    if name == "session_decisions":
        return _session_rows(session)
    if "rows" in spec:
        return list(spec["rows"]())
    if "path" in spec:
        return [json.loads(line) for line in Path(spec["path"]).read_text().splitlines() if line.strip()]
    return _store_rows(spec["memory_type"], scope, session)


def catalogue(session, scope: str) -> list[dict]:
    out = []
    for name, spec in TABLES.items():
        try:
            count = len(rows_of(name, session, scope))
        except Exception:  # noqa: BLE001 — a missing file shows as unknown
            count = -1
        out.append({"name": name, "group": spec["group"], "role": spec["role"], "rows": count})
    return out


def page(name: str, session, scope: str, offset: int, limit: int) -> dict:
    if name not in TABLES:
        raise KeyError(name)
    limit = max(1, min(limit, MAX_LIMIT))
    rows = rows_of(name, session, scope)
    window = rows[offset:offset + limit]
    columns: list[str] = []
    for row in window or rows[:1]:
        for key in row:
            if key not in columns and key not in _SKIP:
                columns.append(key)
    columns = columns[:MAX_COLUMNS]
    return {"table": name, "role": TABLES[name]["role"], "columns": columns, "total": len(rows), "offset": offset,
            "rows": [{c: _clean(r.get(c)) for c in columns} for r in window]}
