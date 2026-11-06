"""One lab session: a scoped id, every decision it asked, and its own MemoRizz store.

The store is a `FileSystemProvider` at `memory_store/appbook-<session>`, the same provider the
notebooks use, so the knowledge base and the toolbox here are built exactly as theirs were. Decisions
are appended to `appbook/data/sessions/<session>.jsonl`. Both are kept when a session ends; set
`DM_CLEANUP=1` to delete them on reset and on shutdown.
"""
from __future__ import annotations

import json
import secrets
import shutil
import threading
import time
from collections import deque
from datetime import datetime, timezone
from typing import Any

import harness

from backend.config import DATA_DIR, settings

SESSIONS_DIR = DATA_DIR / "sessions"


def _trim(value: Any, limit: int = 2000) -> Any:
    """Keep the log readable: long strings are cut, vectors never stored."""
    if isinstance(value, str):
        return value if len(value) <= limit else value[:limit] + "…"
    if isinstance(value, dict):
        return {k: _trim(v, limit) for k, v in value.items() if k != "embedding"}
    if isinstance(value, list):
        return [_trim(v, limit) for v in value[:200]]
    return value


class LabSession:
    def __init__(self) -> None:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        self.id = f"dm-app-{stamp}-{secrets.token_hex(2)}"
        self.started = datetime.now(timezone.utc).isoformat(timespec="seconds")
        self.calls: list[dict] = []
        self.activity: deque = deque(maxlen=200)
        self.cache: dict[str, Any] = {}
        self.lock = threading.RLock()
        self._provider = None
        SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
        self.log_path = SESSIONS_DIR / f"{self.id}.jsonl"

    # ── the MemoRizz store ──────────────────────────────────────────────
    @property
    def store_path(self):
        return harness.STORE / f"appbook-{self.id}"

    def provider(self):
        with self.lock:
            if self._provider is None:
                from memorizz import FileSystemConfig, FileSystemProvider

                self._provider = FileSystemProvider(FileSystemConfig(root_path=self.store_path))
                self.note("write", f"created the MemoRizz store {self.store_path.name}")
            return self._provider

    # ── the decision log ────────────────────────────────────────────────
    def note(self, op: str, what: str) -> None:
        self.activity.appendleft({"at": time.strftime("%H:%M:%S"), "op": op, "what": what})

    def record(self, page: str, records: dict[str, dict], summary: str = "") -> dict:
        """Log one decision request: one entry per backend that answered (or failed)."""
        entry = {"at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "n": len(self.calls) + 1,
                 "page": page, "summary": summary, "calls": {}}
        for name, rec in records.items():
            entry["calls"][name] = {k: rec.get(k) for k in ("label", "model", "ms", "input_tokens", "usd", "error",
                                                         "request", "answers", "raw", "kind", "count")}
        entry = _trim(entry)
        with self.lock:
            self.calls.append(entry)
            with self.log_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(entry, default=str) + "\n")
        labels = ", ".join(rec.get("label", name) for name, rec in records.items())
        self.note("decide", f"{page}: {summary[:60]} → {labels}")
        return entry

    def last(self) -> dict | None:
        return self.calls[-1] if self.calls else None

    def close(self) -> None:
        if settings.cleanup:
            shutil.rmtree(self.store_path, ignore_errors=True)
            self.log_path.unlink(missing_ok=True)


_current = LabSession()
_switch = threading.Lock()


def current() -> LabSession:
    return _current


def reset() -> LabSession:
    """Start a new session. The old one's store and log stay unless DM_CLEANUP=1."""
    global _current
    with _switch:
        _current.close()
        _current = LabSession()
    return _current
