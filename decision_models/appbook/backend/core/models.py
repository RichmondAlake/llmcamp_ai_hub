"""The three decision models behind one call.

`harness.d1` switches backends with a process-wide setting, which suits a notebook and not a server
answering several pages at once. So this module calls the same pieces directly: `system_one` on the
local model, and `harness.d1._post` for Jev and OpenAI, with OpenAI's request and answers translated
by the harness's own functions. Every call returns one record: answers in d1's shape, the request
as the provider received it, the raw reply, latency, input tokens and cost.
"""
from __future__ import annotations

import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable

from harness import d1, measure

from backend.config import BACKENDS, settings

_gpu = threading.Lock()                 # one forward pass at a time on the local model
_loading = threading.Lock()
LOCAL = {"state": "not loaded", "device": None, "seconds": None, "error": None}


def label(name: str) -> str:
    return BACKENDS[name]["label"] if name in BACKENDS else name


def batch_record(name: str, run: dict, count: int) -> dict:
    """A batch run as one log entry, so Tokenomics counts its tokens and cost."""
    return {"label": label(name), "ms": run["wall_ms"], "input_tokens": run["input_tokens"], "usd": run["usd"],
            "kind": "batch", "count": count, "model": d1.served_by.get(name, BACKENDS[name]["model"])}


def available(name: str) -> bool:
    if name == "local":
        return LOCAL["state"] != "failed"
    return bool(os.environ.get(BACKENDS[name]["key"] or ""))


def status() -> dict:
    out = {}
    for name, spec in BACKENDS.items():
        if name == "local":
            state = LOCAL["state"]
        else:
            state = "ready" if available(name) else f"no {spec['key']}"
        out[name] = {"label": spec["label"], "maker": spec["maker"], "model": d1.served_by.get(name, spec["model"]),
                     "where": spec["where"] if name != "local" else (LOCAL["device"] or spec["where"]),
                     "state": state, "available": available(name), "color": spec["color"]}
    out["local"].update(load_seconds=LOCAL["seconds"], error=LOCAL["error"])
    return out


def load_local() -> None:
    """Load d1-2B once (about 7 GB). Later calls return at once."""
    if LOCAL["state"] == "loaded":
        return
    with _loading:
        if LOCAL["state"] == "loaded":
            return
        LOCAL.update(state="loading", error=None)
        started = time.perf_counter()
        try:
            d1.model()
        except Exception as exc:  # noqa: BLE001 — health reports it; hosted models still work
            LOCAL.update(state="failed", error=f"{type(exc).__name__}: {exc}"[:300])
            raise
        LOCAL.update(state="loaded", device=d1.device(), seconds=round(time.perf_counter() - started, 1))


def load_in_background() -> None:
    def run() -> None:
        try:
            load_local()
        except Exception:  # noqa: BLE001 — recorded in LOCAL
            pass
    threading.Thread(target=run, daemon=True).start()


def wanted(backends: list[str] | None) -> list[str]:
    """The requested backends that can answer now, in display order."""
    names = [b for b in BACKENDS if not backends or b in backends]
    return [b for b in names if available(b)]


def request_view(name: str, state: Any, questions: dict) -> dict:
    """The request body the provider receives (keys excluded)."""
    spec = d1.REMOTE.get(name)
    if name == "openai":
        evidence = state if isinstance(state, str) else [
            {"role": "user", "content": [{"type": "input_json", "data": state}]}]
        return {"model": spec["model"], "input": evidence,
                "questions": [d1._openai_question(n, q) for n, q in questions.items()]}
    model = spec["model"] if spec else f"{d1.MODEL_ID}@{d1.REVISION[:8]}"
    return {"model": model, "state": state, "questions": questions}


def _call(name: str, state: Any, questions: dict) -> tuple[dict, int, Any]:
    if name == "local":
        load_local()
        with _gpu:
            result = d1.model().system_one(state, questions)
        return result["answers"], int(result["usage"]["input_tokens"]), None
    if name == "jev":
        raw = d1._post("jev", {"state": state, "questions": questions})
        return raw["answers"], int(raw["usage"]["input_tokens"]), raw
    body = request_view("openai", state, questions)
    raw = d1._post("openai", {"input": body["input"], "questions": body["questions"]})
    answers = {a["name"]: d1._openai_answer(a, questions[a["name"]]) for a in raw["answers"]}
    return answers, int(raw["usage"]["input_tokens"]), raw


def price(name: str, tokens: int) -> float:
    """At each provider's input price. Local d1 is priced at Liquid's hosted rate, as in the notebooks."""
    return measure.price(d1.price_model(name), tokens)


def ask(name: str, state: Any, questions: dict) -> dict:
    """One state, one set of questions, one backend. Errors come back in the record, not raised."""
    record = {"backend": name, "label": BACKENDS[name]["label"]}
    started = time.perf_counter()
    try:
        answers, tokens, raw = _call(name, state, questions)
    except Exception as exc:  # noqa: BLE001 — a page shows the other backends' answers
        return {**record, "error": f"{type(exc).__name__}: {exc}"[:300], "ms": (time.perf_counter() - started) * 1000}
    return {**record, "answers": answers, "ms": (time.perf_counter() - started) * 1000, "input_tokens": tokens,
            "usd": price(name, tokens), "model": d1.served_by.get(name, BACKENDS[name]["model"]),
            "request": request_view(name, state, questions), "raw": raw}


def ask_all(backends: list[str], state: Any, questions: dict) -> dict[str, dict]:
    """The same request to every backend, in parallel. Each latency is that backend's own."""
    if not backends:
        return {}
    with ThreadPoolExecutor(len(backends)) as pool:
        futures = {name: pool.submit(ask, name, state, questions) for name in backends}
    return {name: future.result() for name, future in futures.items()}


def ask_many(name: str, items: list[tuple[Any, dict]], progress: Callable[[int, int], None] | None = None) -> dict:
    """Many requests to one backend: local runs share forward passes, hosted ones run eight at a time.

    Returns the answers in order, the median latency per request, total tokens and cost.
    """
    answers: list[dict | None] = [None] * len(items)
    times: list[float] = []
    tokens = 0
    errors = 0
    started = time.perf_counter()
    if name == "local":
        load_local()
        for start in range(0, len(items), d1.BATCH_SIZE):
            batch = items[start:start + d1.BATCH_SIZE]
            t0 = time.perf_counter()
            with _gpu:
                results = d1.model().system_one_batch(batch)
            each = (time.perf_counter() - t0) * 1000 / len(batch)
            for offset, result in enumerate(results):
                answers[start + offset] = result["answers"]
                tokens += int(result["usage"]["input_tokens"])
                times.append(each)
            if progress:
                progress(min(start + len(batch), len(items)), len(items))
    else:
        done = 0
        lock = threading.Lock()

        def one(index: int) -> None:
            nonlocal tokens, done, errors
            t0 = time.perf_counter()
            try:
                result, used, _ = _call(name, *items[index])
            except Exception:  # noqa: BLE001 — counted; the item scores as unanswered
                result, used = None, 0
                with lock:
                    errors += 1
            with lock:
                answers[index] = result
                tokens += used
                times.append((time.perf_counter() - t0) * 1000)
                done += 1
                if progress:
                    progress(done, len(items))

        with ThreadPoolExecutor(settings.hosted_workers) as pool:
            list(pool.map(one, range(len(items))))
    times.sort()
    return {"answers": answers, "ms_median": times[len(times) // 2] if times else None,
            "wall_ms": (time.perf_counter() - started) * 1000, "input_tokens": tokens,
            "usd": price(name, tokens), "errors": errors}
