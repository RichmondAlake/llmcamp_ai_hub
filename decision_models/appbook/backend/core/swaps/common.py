"""Shared pieces of the seven swap pages: embeddings, the chat model, and the method record.

Every page compares "today" with each chosen decision model, and every method comes back as one
record the frontend draws the same way: an answer, whether it was right (when the labels know), a
few lines of detail, and its latency, tokens and cost. Decision-model records also carry the
request as the provider received it, for the Model context rail.
"""
from __future__ import annotations

import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable

import harness
import numpy as np
from harness import measure

from backend.config import BACKENDS, TYPICAL_COLOR
from backend.core import models

_embeddings = None
_vectors: dict[str, np.ndarray] = {}
_vec_lock = threading.Lock()
_llm = None
_llm_lock = threading.Lock()


def openai_ready() -> bool:
    return bool(os.environ.get("OPENAI_API_KEY"))


def embed(texts: list[str]) -> np.ndarray:
    """Unit vectors from the notebooks' embedding model, cached by text for the life of the server."""
    global _embeddings
    missing = [t for t in dict.fromkeys(texts) if t not in _vectors]
    if missing:
        if _embeddings is None:
            from langchain_openai import OpenAIEmbeddings

            _embeddings = OpenAIEmbeddings(model=harness.EMBEDDING_MODEL)
        vectors = np.array(_embeddings.embed_documents(missing))
        vectors /= np.linalg.norm(vectors, axis=1, keepdims=True)
        with _vec_lock:
            _vectors.update(zip(missing, vectors))
    return np.array([_vectors[t] for t in texts])


def embed_usd(texts: list[str]) -> float:
    return measure.price(harness.EMBEDDING_MODEL, measure.embedding_tokens(texts))


def llm():
    global _llm
    if _llm is None:
        from memorizz.llms.llm_factory import create_llm_provider

        _llm = create_llm_provider({"provider": "openai", "model": harness.CHAT_MODEL})
    return _llm


def generate(prompt: str) -> tuple[str, int, int]:
    """One chat completion and its token counts (the provider keeps only its last usage)."""
    with _llm_lock:
        text = llm().generate_text(prompt)
        usage = llm().get_last_usage() or {}
    return text, int(usage.get("prompt_tokens") or 0), int(usage.get("completion_tokens") or 0)


def today(label: str, run: Callable[[], dict]) -> dict:
    """Run a typical method and time it. `run` returns answer, right, lines, and optionally usd/tokens."""
    record = {"key": "typical", "label": label, "color": TYPICAL_COLOR}
    started = time.perf_counter()
    try:
        out = run()
    except Exception as exc:  # noqa: BLE001 — the page still shows the decision models
        return {**record, "error": f"{type(exc).__name__}: {exc}"[:300], "ms": (time.perf_counter() - started) * 1000}
    return {**record, "ms": (time.perf_counter() - started) * 1000, **out}


def model_record(name: str, rec: dict, answer: str, right: bool | None, lines: list[dict]) -> dict:
    """A decision model's result in the page shape, keeping what the context rail needs."""
    out = {"key": name, "label": BACKENDS[name]["label"], "color": BACKENDS[name]["color"],
           "model": rec.get("model"), "ms": rec.get("ms"), "input_tokens": rec.get("input_tokens"),
           "usd": rec.get("usd"), "request": rec.get("request"), "raw": rec.get("raw")}
    if rec.get("error"):
        return {**out, "error": rec["error"]}
    return {**out, "answer": answer, "right": right, "lines": lines}


def ask_each(backends: list[str], state: Any, questions: dict) -> dict[str, dict]:
    """One request to every chosen backend, in parallel (models.ask_all)."""
    return models.ask_all(backends, state, questions)


def many_each(backends: list[str], items: list[tuple[Any, dict]]) -> dict[str, dict]:
    """Several requests to every chosen backend; each backend runs its own batch, in parallel."""
    if not backends:
        return {}
    with ThreadPoolExecutor(len(backends)) as pool:
        futures = {name: pool.submit(models.ask_many, name, items) for name in backends}
    out = {}
    for name, future in futures.items():
        run = future.result()
        out[name] = {"answers": run["answers"], "ms": run["wall_ms"], "input_tokens": run["input_tokens"],
                     "usd": run["usd"], "model": BACKENDS[name]["model"], "errors": run["errors"],
                     "request": models.request_view(name, *items[0]) if items else None, "raw": None}
        if run["errors"] == len(items):
            out[name]["error"] = "every request failed"
    return out


def log(session, page: str, methods: list[dict], summary: str) -> None:
    """Log the decision-model calls of one try, so Tokenomics and the context rail see them."""
    records = {m["key"]: {k: m.get(k) for k in ("label", "model", "ms", "input_tokens", "usd", "error", "request", "raw")}
               for m in methods if not m["key"].startswith("typical")}
    for m in methods:
        if not m["key"].startswith("typical") and not m.get("error"):
            records[m["key"]]["answers"] = {"answer": m.get("answer")}
    if records:
        session.record(page, records, summary=summary)


def labelled_run(session, page: str, name: str, items: list[tuple[Any, dict]], score: Callable[[list], dict],
                 progress) -> dict:
    """A whole label set through one backend, scored, and logged as one batch."""
    run = models.ask_many(name, items, progress)
    result = score(run["answers"])
    session.record(page, {name: {**models.batch_record(name, run, len(items)),
                                 "request": models.request_view(name, *items[0])}},
                   summary=f"labelled set, {len(items)} requests")
    return {**result, "backend": name, "label": BACKENDS[name]["label"], "requests": len(items),
            "seconds": round(run["wall_ms"] / 1000, 1), "ms_median": run["ms_median"], "usd": run["usd"],
            "errors": run["errors"]}
