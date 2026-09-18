"""Session-scoped journals, immutable offloads and evidence search.

Adapted from agent_memory_from_scratch.ipynb. API items stay separate from
provenance metadata. The manifest is an atomic projection; journals are primary
evidence and are always written before an item enters the active context.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path


def uid():
    return uuid.uuid4().hex


def checked_id(value):
    if uuid.UUID(value).hex != value:
        raise ValueError("Invalid memory identifier.")
    return value


def now():
    return datetime.now(timezone.utc).isoformat()


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def message(text, role="user"):
    return {"role": role, "content": text}


def item_text(item):
    kind = item.get("type", "message")
    if kind == "reasoning":
        return "[Opaque reasoning state; preserved for the API, not displayed.]"
    if kind == "function_call":
        return f"{item['name']}({item['arguments']})"
    if kind == "function_call_output":
        return str(item["output"])
    content = item.get("content", "")
    return content if isinstance(content, str) else "\n".join(
        part.get("text", part.get("refusal", "")) for part in content
    )


def visible_items(items):
    return [i for i in items if i.get("type") != "reasoning"]


def balanced_tools(items):
    calls = [i["call_id"] for i in items if i.get("type") == "function_call"]
    results = [i["call_id"] for i in items if i.get("type") == "function_call_output"]
    return len(set(calls)) == len(calls) and sorted(calls) == sorted(results)


class MemoryStore:
    def __init__(self, data_dir):
        self.data_dir = Path(data_dir).resolve()
        self.root = self.data_dir / "memory" / "long_term" / "episodic"
        self.root.mkdir(parents=True, exist_ok=True)
        self._locks = {}
        self._guard = threading.Lock()

    def lock(self, session_id):
        checked_id(session_id)
        with self._guard:
            return self._locks.setdefault(session_id, threading.Lock())

    def folder(self, session_id):
        return self.root / "conversation" / checked_id(session_id)

    def journal(self, state, window_id=None):
        return self.folder(state["id"]) / checked_id(window_id or state["window_id"]) / "events.jsonl"

    @staticmethod
    def atomic_json(path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        with temporary.open("w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(path)

    def save(self, state):
        state["updated_at"] = now()
        self.atomic_json(self.folder(state["id"]) / "manifest.json", state)

    def load(self, session_id):
        path = self.folder(session_id) / "manifest.json"
        if not path.exists():
            raise FileNotFoundError("Session not found.")
        return json.loads(path.read_text(encoding="utf-8"))

    def create(self, mode, model, effort, budget, notes_budget, diagnostic_checks, group_id=None):
        identifier = uid()
        state = {
            "id": identifier, "notes_id": identifier, "mode": mode,
            "model": model, "effort": effort, "budget": budget,
            "notes_budget": notes_budget, "diagnostic_checks": diagnostic_checks,
            "diagnostic_marker": "TRACE-" + uid(), "group_id": group_id,
            "created_at": now(), "updated_at": now(), "windows": [],
            "context": [], "messages": [], "trace": [], "reductions": [],
            "usage": [], "count_calls": 0, "window_tokens": {},
            "status": "Ready", "error": None, "exported_windows": [],
            "auto_rollover": mode == "notes",
        }
        self.rotate(state, [])
        return state

    def append(self, state, item, origin="original"):
        path = self.journal(state)
        event = {
            "event_id": uid(), "session_id": state["id"],
            "context_window_id": state["window_id"],
            "window_number": len(state["windows"]), "origin": origin,
            "created_at": now(), "item": copy.deepcopy(item),
        }
        with path.open("a", encoding="utf-8") as stream:
            stream.write(encoded(event) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        state["context"].append(copy.deepcopy(item))
        self.save(state)
        return event

    def rotate(self, state, seeds):
        state["window_id"] = uid()
        state["windows"].append({"id": state["window_id"], "created_at": now()})
        state["context"] = []
        path = self.journal(state)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch(exist_ok=False)
        for seed in seeds:
            self.append(state, seed, "seed")
        self.save(state)

    def events(self, state, window_id=None):
        path = self.journal(state, window_id)
        events = []
        raw = path.read_text(encoding="utf-8")
        lines = raw.splitlines()
        # A polling reader can overlap an append. An unfinished last line is not
        # yet an event; display it only after the terminating newline is written.
        if raw and not raw.endswith("\n"):
            lines = lines[:-1]
        for number, line in enumerate(lines, 1):
            event = json.loads(line)
            events.append({**event, "source": str(path.relative_to(self.root)), "line": number})
        return events

    def note_path(self, state):
        return self.root / "notes" / f"{checked_id(state['notes_id'])}.txt"

    def notes(self, state):
        path = self.note_path(state)
        if not path.exists():
            return []
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]

    def append_notes(self, state, notes):
        path = self.note_path(state)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as stream:
            for note in notes:
                stream.write(encoded(note) + "\n")
            stream.flush()
            os.fsync(stream.fileno())

    def store_offload(self, state, identifier, items):
        payload = {"session_id": state["id"], "source_window_id": state["window_id"], "items": items}
        record = {"payload": payload, "sha256": hashlib.sha256(encoded(payload).encode()).hexdigest()}
        path = self.root / "offloaded_context" / state["id"] / f"{checked_id(identifier)}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("x", encoding="utf-8") as stream:
            stream.write(encoded(record))

    def read_offload(self, state, offload_id):
        path = self.root / "offloaded_context" / state["id"] / f"{checked_id(offload_id)}.json"
        record = json.loads(path.read_text(encoding="utf-8"))
        payload = record["payload"]
        if payload["session_id"] != state["id"]:
            raise ValueError("Offload belongs to another session.")
        if hashlib.sha256(encoded(payload).encode()).hexdigest() != record["sha256"]:
            raise ValueError("Offload integrity check failed.")
        return payload

    def retrieve(self, state, offload_id, query="", start=0, max_chars=2400):
        if start < 0 or not 1 <= max_chars <= 4000:
            raise ValueError("Use start >= 0 and a page of at most 4,000 characters.")
        payload = self.read_offload(state, offload_id)
        text = encoded(visible_items(payload["items"]))
        if query:
            match = text.casefold().find(query.casefold(), start)
            if match < 0:
                return {"found": False, "offload_id": offload_id, "excerpt": ""}
            start = max(start, match - 160)
        end = min(start + max_chars, len(text))
        return {"found": start < len(text), "offload_id": offload_id,
                "source_window_id": payload["source_window_id"], "start": start,
                "next_start": end, "has_more": end < len(text),
                "total_chars": len(text), "excerpt": text[start:end]}

    def search(self, state, query, target="session"):
        if not query.strip() or "\n" in query or len(query) > 200:
            raise ValueError("Use a short, nonempty, single-line literal query.")
        rows = []
        if target == "notes":
            for line, note in enumerate(self.notes(state), 1):
                rows.append({**note, "source": str(self.note_path(state).relative_to(self.root)),
                             "line": line, "origin": "note", "text": encoded(note)})
        else:
            # Closed windows only; seed copies and retrieval results are not originals.
            for window in state["windows"][:-1]:
                for event in self.events(state, window["id"]):
                    if event["origin"] == "original" and event["item"].get("type") != "reasoning":
                        rows.append({**event, "text": item_text(event["item"])})
        hits = []
        for row in rows:
            match = row["text"].casefold().find(query.casefold())
            if match >= 0:
                start = max(0, match - 120)
                hits.append({"source": row["source"], "line": row["line"],
                             "window_number": row["window_number"],
                             "window_id": row.get("context_window_id", row.get("window_id")),
                             "timestamp": row["created_at"], "origin": row["origin"],
                             "role": row.get("item", {}).get("role", "tool_or_note"),
                             "excerpt": row["text"][start:start + 1000]})
        hits.sort(key=lambda h: (h["window_number"], h["line"]), reverse=True)
        return hits[:5]

    def public(self, state):
        result = {k: copy.deepcopy(v) for k, v in state.items() if k not in {"context", "diagnostic_marker"}}
        result["notes"] = self.notes(state)
        result["windows"] = []
        for number, window in enumerate(state["windows"], 1):
            events = self.events(state, window["id"])
            result["windows"].append({
                **window, "number": number, "active": window["id"] == state["window_id"],
                "tokens": state["window_tokens"].get(window["id"]),
                "items": [{"event_id": e["event_id"], "origin": e["origin"],
                           "kind": e["item"].get("type", "message"),
                           "role": e["item"].get("role", "tool"),
                           "created_at": e["created_at"], "text": item_text(e["item"]),
                           "call_id": e["item"].get("call_id"), "source": e["source"],
                           "line": e["line"]} for e in events],
            })
        return result
