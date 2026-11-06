"""One way of measuring every swap: wall-clock time, tokens and cost, appended to results/.

Notebook 08 and the appbook read these files and nothing else, so a typical call and a decision call
land in the same table with the same columns.
"""

from __future__ import annotations

import json
import time
from contextlib import contextmanager
from typing import Any, Callable, Iterator

from . import CHAT_MODEL, EMBEDDING_MODEL, RESULTS

#: US dollars per million tokens: (input, output). Checked on 2026-11-01 against
#: liquid.ai/pricing and developers.openai.com/api/docs/models. gpt-6-luna is the Decisions API rate
#: for uncached input (developers.openai.com, 2026-11-06). Jev's rate is the one TypeSafe states on
#: its home page ($42 per billion input tokens), checked 2026-11-06; it has no pricing page.
PRICES: dict[str, tuple[float, float]] = {
    "d1.1": (0.02, 0.0),
    "jev": (0.042, 0.0),
    "gpt-6-luna": (0.10, 0.0),
    "gpt-4o-mini": (0.15, 0.60),
    "text-embedding-3-small": (0.02, 0.0),
    "local": (0.0, 0.0),
}

_notebook = "scratch"


def use_notebook(name: str, fresh: bool = True) -> None:
    """Point this process at results/<name>.jsonl, cleared by default so a re-run replaces it."""
    global _notebook
    _notebook = name
    RESULTS.mkdir(exist_ok=True)
    if fresh:
        path().unlink(missing_ok=True)


def path():
    return RESULTS / f"{_notebook}.jsonl"


def record(**row: Any) -> dict:
    """Append one row to the current notebook's results file."""
    row = {"notebook": _notebook, **row}
    with path().open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row) + "\n")
    return row


@contextmanager
def timed(label: str, count: int = 1, **extra: Any) -> Iterator[dict]:
    """Time a block. `count` is how many decisions it held, so per-decision latency is honest."""
    result: dict[str, Any] = {}
    started = time.perf_counter()
    try:
        yield result
    finally:
        result["seconds"] = time.perf_counter() - started
        record(kind="time", label=label, seconds=result["seconds"], count=count, **extra)


def price(model: str, input_tokens: int, output_tokens: int = 0) -> float:
    rate_in, rate_out = PRICES[model]
    return (input_tokens * rate_in + output_tokens * rate_out) / 1_000_000


def cost(label: str, input_tokens: int, output_tokens: int = 0, model: str = CHAT_MODEL, **extra: Any) -> float:
    """Record tokens and their price. Raises on a model with no price rather than guessing one."""
    usd = price(model, input_tokens, output_tokens)
    record(kind="cost", label=label, model=model, input_tokens=input_tokens,
           output_tokens=output_tokens, usd=usd, **extra)
    return usd


def metric(label: str, name: str, value: float, **extra: Any) -> None:
    """Record an accuracy-style result."""
    record(kind="metric", label=label, name=name, value=value, **extra)


def per_item(label: str, name: str, values: Any, **extra: Any) -> None:
    """Record one score per question or turn, so results can be bootstrapped and paired."""
    record(kind="per_item", label=label, name=name, values=[float(value) for value in values], **extra)


def counted(llm: Any, label: str, model: str = CHAT_MODEL) -> Callable[[str], str]:
    """A `generate(prompt)` on a memorizz LLM that times and prices every call."""

    def generate(prompt: str) -> str:
        with timed(label):
            text = llm.generate_text(prompt)
        tokens = llm.get_last_usage() or {}
        cost(label, tokens.get("prompt_tokens") or 0, tokens.get("completion_tokens") or 0, model=model)
        return text

    return generate


def embedding_tokens(texts: list[str]) -> int:
    """The tokens an embedding call bills for these texts."""
    import tiktoken

    encoder = tiktoken.encoding_for_model(EMBEDDING_MODEL)
    return sum(len(encoder.encode(text)) for text in texts)


def _verdict(today_items: list[float], model_items: list[float], higher_is_better: bool,
             draws: int = 2000, seed: int = 7) -> tuple[str, float, float]:
    """better, level or worse: a paired bootstrap on the per-item scores, 95% interval."""
    import numpy as np

    today, model = np.asarray(today_items, float), np.asarray(model_items, float)
    diff = (model - today) if higher_is_better else (today - model)
    rng = np.random.default_rng(seed)
    means = diff[rng.integers(0, len(diff), (draws, len(diff)))].mean(axis=1)
    low, high = np.percentile(means, [2.5, 97.5])
    return ("better" if low > 0 else "worse" if high < 0 else "level"), float(low), float(high)


def scorecard(swap: str, measure_name: str, today_label: str, model_label: str,
              today_items: list[float], model_items: list[float], *, higher_is_better: bool = True,
              also: dict[str, tuple[list[float], list[float]]] | None = None,
              extra: dict[str, tuple[Any, Any]] | None = None) -> dict:
    """Print the swap's result as one obvious block and record it for notebook 08 and the appbook.

    `today_items` and `model_items` are one score per labelled item, in the same order, so the
    verdict compares the two methods on the same items. `also` adds more measures judged the same way
    (higher is better). `extra` adds rows such as latency and cost, each a (today, model) pair,
    already formatted or numeric, with no verdict.
    """
    import numpy as np

    judged = {measure_name: (today_items, model_items, higher_is_better)}
    judged.update({name: (a, b, True) for name, (a, b) in (also or {}).items()})
    verdicts = {name: _verdict(a, b, up) for name, (a, b, up) in judged.items()}
    rows = [(name, f"{np.mean(a):.2f}", f"{np.mean(b):.2f}") for name, (a, b, _) in judged.items()]
    for name, (a, b) in (extra or {}).items():
        rows.append((name, a if isinstance(a, str) else f"{a:,.4g}", b if isinstance(b, str) else f"{b:,.4g}"))
    width = max(len(r[0]) for r in rows) + 2
    a_w = max(len(today_label), *(len(r[1]) for r in rows)) + 2
    line = "=" * max(len(swap), width + a_w + max(len(model_label), *(len(r[2]) for r in rows)) + 2)
    words = {"better": "BETTER", "level": "LEVEL (the gap is within noise)", "worse": "WORSE"}
    print(line)
    print(swap)
    print(line)
    print(f"{'':{width}}{today_label:<{a_w}}{model_label}")
    for name, a, b in rows:
        print(f"{name:<{width}}{a:<{a_w}}{b}")
    print(line)
    for name, (verdict, low, high) in verdicts.items():
        print(f"Decision model on {name}: {words[verdict]}")
        print(f"   paired bootstrap over {len(judged[name][0])} items, 95% interval of the gain {low:+.2f} to {high:+.2f}")
    print(line)
    verdict, low, high = verdicts[measure_name]
    return record(kind="summary", swap=swap, measure=measure_name, today_label=today_label,
                  model_label=model_label, today=float(np.mean(today_items)), model=float(np.mean(model_items)),
                  verdict=verdict, low=low, high=high, higher_is_better=higher_is_better, n=len(today_items),
                  also={name: {"today": float(np.mean(judged[name][0])), "model": float(np.mean(judged[name][1])),
                               "verdict": v[0], "low": v[1], "high": v[2]}
                        for name, v in verdicts.items() if name != measure_name},
                  extra={k: [str(a), str(b)] for k, (a, b) in (extra or {}).items()})
