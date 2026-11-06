"""The decision model, loaded once.

Every notebook asks through `decide` and `decide_batch`, so the backend is one environment variable:

    D1_BACKEND=local    LiquidAI/d1-2B through Transformers (the default)
    D1_BACKEND=hosted   Liquid's d1.1 over HTTP (needs LIQUID_API_KEY)
    D1_BACKEND=jev      TypeSafe's Jev over HTTP (needs TYPESAFE_API_KEY)
    D1_BACKEND=openai   OpenAI's Decisions API, gpt-6-luna (needs OPENAI_API_KEY)

`with d1.using("jev"):` switches the backend for a block, which is how notebook 09 asks three
decision models the same questions.

All four return the same answers. A noul answer carries P(yes); a choice answer carries its pick,
the pick's confidence and every option's probability; a score answer carries a level and a legend.
Liquid and Jev share one request shape. OpenAI's differs, and `_openai` translates both ways.
"""

from __future__ import annotations

import os
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager

# On Apple silicon the GPU shares memory with everything else. A ceiling makes an oversized batch
# raise an error instead of paging out the whole machine.
os.environ.setdefault("PYTORCH_MPS_HIGH_WATERMARK_RATIO", "0.7")
os.environ.setdefault("PYTORCH_MPS_LOW_WATERMARK_RATIO", "0.5")
from typing import Any, Iterable, Iterator

MODEL_ID = "LiquidAI/d1-2B"
REVISION = "10e7671d44e4b37700020b1eed3f594c5f2af0b4"
HOSTED_WORKERS = 8
BATCH_SIZE = int(os.environ.get("D1_BATCH_SIZE", "32"))
#: Padded tokens in one forward pass. The model's default of 65,536 suits a data-centre GPU; on a
#: 16 GB laptop, long states at that budget thrash the whole machine.
TOKEN_BUDGET = int(os.environ.get("D1_TOKEN_BUDGET", "6000"))

#: The hosted backends: endpoint, key, model, and the name measure.PRICES knows it by.
REMOTE = {
    "hosted": {"url": "https://api.liquid.ai/decisions/v1/systemone", "key": "LIQUID_API_KEY",
               "model": "d1.1", "price": "d1.1"},
    "jev": {"url": "https://api.typesafe.ai/v1/systemone", "key": "TYPESAFE_API_KEY",
            "model": os.environ.get("JEV_MODEL", "jev-1.14.0"), "price": "jev"},
    "openai": {"url": "https://api.openai.com/v1/decisions", "key": "OPENAI_API_KEY",
               "model": os.environ.get("OPENAI_DECISIONS_MODEL", "gpt-6-luna"), "price": "gpt-6-luna"},
}
HOSTED_URL = REMOTE["hosted"]["url"]
HOSTED_MODEL = REMOTE["hosted"]["model"]

_model = None
_device = None
_override: str | None = None

#: Running totals, read by the notebooks to price a block of decisions.
usage = {"requests": 0, "questions": 0, "input_tokens": 0, "refusals": 0, "retries": 0}
#: The model each backend says answered, e.g. jev-latest resolves to a version.
served_by: dict[str, str] = {}


def backend() -> str:
    return _override or os.environ.get("D1_BACKEND", "local").strip().lower()


@contextmanager
def using(name: str) -> Iterator[None]:
    """Send every decision in this block to one backend: local, hosted, jev or openai."""
    global _override
    if name != "local" and name not in REMOTE:
        raise ValueError(f"unknown backend {name!r}")
    previous, _override = _override, name
    try:
        yield
    finally:
        _override = previous


def price_model(name: str | None = None) -> str:
    """The key in measure.PRICES for a backend. Local runs are priced at Liquid's hosted rate."""
    name = name or backend()
    return REMOTE[name]["price"] if name in REMOTE else "d1.1"


def model():
    """The local model, loaded on first use and kept for the life of the process."""
    global _model, _device
    if _model is None:
        import torch
        from transformers import AutoModel

        _device = "cuda" if torch.cuda.is_available() else ("mps" if torch.backends.mps.is_available() else "cpu")
        dtype = torch.float32 if _device == "cpu" else torch.bfloat16
        _model = AutoModel.from_pretrained(
            MODEL_ID, revision=REVISION, trust_remote_code=True, dtype=dtype
        ).to(_device)
        if _device != "cuda":
            _model.engine.token_budget = TOKEN_BUDGET
    return _model


def device() -> str | None:
    return _device


def compile_model() -> None:
    """Warm, compiled calls. Optional, and only meaningful on the local backend."""
    if backend() == "local":
        model().compile()


def _count(results: Iterable[dict], questions: int) -> None:
    results = list(results)
    usage["requests"] += len(results)
    usage["questions"] += questions
    usage["input_tokens"] += sum(r["usage"]["input_tokens"] for r in results)


def _post(name: str, body: dict) -> dict:
    import requests

    spec = REMOTE[name]
    key = os.environ.get(spec["key"])
    if not key:
        raise RuntimeError(f"D1_BACKEND={name} needs {spec['key']} in .env")
    # Retry rate limits, server errors and stalled connections; a hosted call can hang now and then.
    for attempt in range(4):
        try:
            response = requests.post(spec["url"], headers={"Authorization": f"Bearer {key}"},
                                     json={"model": spec["model"], **body}, timeout=30)
        except (requests.Timeout, requests.ConnectionError):
            if attempt == 3:
                raise
            usage["retries"] = usage.get("retries", 0) + 1
            continue
        if response.status_code not in (429, 500, 502, 503, 504) or attempt == 3:
            break
        usage["retries"] = usage.get("retries", 0) + 1
        time.sleep(2 ** attempt)
    if not response.ok:
        raise RuntimeError(f"{name} returned HTTP {response.status_code}: {response.text[:300]}")
    result = response.json()
    served_by[name] = result.get("model", spec["model"])
    return result


def _system_one(name: str, state: Any, questions: dict) -> dict:
    """Liquid and Jev: the same request and answer shape as the local model."""
    return _post(name, {"state": state, "questions": questions})


def _openai_question(name: str, question: dict) -> dict:
    kind = question["type"]
    text = question["instructions"]
    criteria = question.get("criteria")
    converted: dict[str, Any] = {"type": "predicate" if kind == "noul" else kind, "name": name}
    if kind == "noul" and criteria:
        # A predicate has no criteria field, so what yes and no mean goes into the instructions.
        text += f"\nTrue when: {criteria['true']}\nFalse when: {criteria['false']}"
    elif kind == "choice":
        converted["choices"] = [{"value": key, "description": value} for key, value in criteria.items()]
    elif kind == "score":
        converted["levels"] = [{"label": str(i), "description": level} for i, level in enumerate(criteria)]
    converted["instructions"] = text
    return converted


def _openai_answer(answer: dict, question: dict) -> dict:
    kind = question["type"]
    if answer.get("type") == "refusal":
        usage["refusals"] += 1
        if kind == "noul":
            return {"type": "noul", "noul": 0.5, "refused": True}
        keys = list(question["criteria"]) if kind == "choice" else [str(i) for i in range(len(question["criteria"]))]
        flat = {key: 1 / len(keys) for key in keys}
        return {"type": kind, "choice": None, "score": None, "confidence": 0.0, "probabilities": flat, "refused": True}
    if kind == "noul":
        return {"type": "noul", "noul": answer["probability"]}
    if kind == "choice":
        return {"type": "choice", "choice": answer["choice"], "confidence": answer["confidence"],
                "probabilities": {item["value"]: item["probability"] for item in answer["probabilities"]}}
    return {"type": "score", "score": answer["score"], "confidence": answer["confidence"],
            "legend": {str(i): level for i, level in enumerate(question["criteria"])},
            "probabilities": {str(item["value"]): item["probability"] for item in answer["probabilities"]}}


def _openai(state: Any, questions: dict) -> dict:
    """OpenAI's Decisions API, with the request and the answers translated to the shape above."""
    if isinstance(state, str):
        evidence: Any = state
    else:
        evidence = [{"role": "user", "content": [{"type": "input_json", "data": state}]}]
    result = _post("openai", {"input": evidence,
                              "questions": [_openai_question(n, q) for n, q in questions.items()]})
    answers = {answer["name"]: _openai_answer(answer, questions[answer["name"]]) for answer in result["answers"]}
    return {"answers": answers, "usage": {"input_tokens": result["usage"]["input_tokens"]},
            "model": result.get("model")}


def _remote(name: str, state: Any, questions: dict) -> dict:
    return _openai(state, questions) if name == "openai" else _system_one(name, state, questions)


def ask(state: Any, questions: dict) -> dict:
    """One state, several named questions. Returns the whole result, usage included."""
    name = backend()
    result = model().system_one(state, questions) if name == "local" else _remote(name, state, questions)
    _count([result], len(questions))
    return result


def ask_batch(items: list[tuple[Any, dict]]) -> list[dict]:
    """Many (state, questions) pairs, each a whole result. Local runs share forward passes."""
    name = backend()
    results: list[dict] = []
    if name != "local":
        with ThreadPoolExecutor(HOSTED_WORKERS) as pool:
            results = list(pool.map(lambda item: _remote(name, *item), items))
    else:
        for start in range(0, len(items), BATCH_SIZE):
            results.extend(model().system_one_batch(items[start : start + BATCH_SIZE]))
    _count(results, sum(len(questions) for _, questions in items))
    return results


def decide(state: Any, questions: dict) -> dict:
    """One state, several named questions. Returns {name: answer}."""
    return ask(state, questions)["answers"]


def decide_batch(items: list[tuple[Any, dict]]) -> list[dict]:
    """Many (state, questions) pairs. Returns a list of {name: answer}."""
    return [result["answers"] for result in ask_batch(items)]


def noul(instructions: str, true: str | None = None, false: str | None = None) -> dict:
    """A yes/no question. The criteria are optional and sharpen what yes and no mean."""
    question: dict[str, Any] = {"type": "noul", "instructions": instructions}
    if true or false:
        question["criteria"] = {"true": true or "yes", "false": false or "no"}
    return question


def choice(instructions: str, options: dict[str, str]) -> dict:
    """One option from a named set."""
    return {"type": "choice", "instructions": instructions, "criteria": dict(options)}


def score(instructions: str, levels: list[str]) -> dict:
    """An ordered scale, lowest level first."""
    return {"type": "score", "instructions": instructions, "criteria": list(levels)}
