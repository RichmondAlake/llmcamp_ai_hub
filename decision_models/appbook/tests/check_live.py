"""Live checks against a running appbook, with the real models.

    ./run.sh &                                   # in another terminal
    ../.venv/bin/python tests/check_live.py      # BASE=http://127.0.0.1:8740 by default

Every swap's first example (the notebook's "where it breaks" case) is asked of today's method and
every available decision model, then one labelled set runs live. A check fails only when no
decision model gets a labelled example right, or a page's data is missing.
"""
from __future__ import annotations

import json
import os
import sys

import httpx

BASE = os.environ.get("BASE", "http://127.0.0.1:8740")
#: Limit the models, e.g. MODELS=jev,openai to leave d1 unloaded on a machine short of memory.
ONLY = [m for m in os.environ.get("MODELS", "").split(",") if m]
client = httpx.Client(base_url=BASE, timeout=600)
results: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok, detail))
    print(f"{'PASS' if ok else 'FAIL'}  {name}  {detail}", flush=True)


def stream(url: str, body: dict) -> dict:
    r = client.post(url, json=body)
    r.raise_for_status()
    lines = r.text.replace("\r\n", "\n").split("\n")
    events = [line.split(":", 1)[1].strip() for line in lines if line.startswith("event:")]
    data = [line[5:].strip() for line in lines if line.startswith("data:")]
    if events and events[-1] == "error":
        raise RuntimeError(json.loads(data[-1])["detail"])
    return json.loads(data[-1])


def main() -> int:
    health = client.get("/api/health").json()
    models = [k for k in health["order"] if health["models"][k]["available"] and (not ONLY or k in ONLY)]
    check("health", bool(models), f"available: {models}; d1 {health['models']['local']['state']}")

    arch = client.get("/api/architecture").json()
    check("architecture", len(arch["points"]) == 20 and arch["built"] == 11 and len(arch["swaps"]) == 7,
          f"{arch['built']} of 20 built; verdicts {[s['verdict'] for s in arch['swaps']]}")

    for swap in client.get("/api/swaps").json()["swaps"]:
        example = swap["examples"][0]["input"]
        body = {"backends": models, **(example if isinstance(example, dict) else {"text": example})}
        d = client.post(f"/api/swaps/{swap['id']}/try", json=body).json()
        today = [m for m in d["methods"] if m["key"].startswith("typical")]
        dms = {m["key"]: m for m in d["methods"] if not m["key"].startswith("typical")}
        errors = [m["error"] for m in d["methods"] if m.get("error")]
        labelled = any(m.get("right") is not None for m in dms.values())
        ok = not errors and set(dms) == set(models) and today and (not labelled or any(m.get("right") for m in dms.values()))
        check(f"swap {swap['n']} · {swap['id']}", bool(ok),
              json.dumps({m["label"]: [m.get("answer"), m.get("right")] for m in d["methods"]})[:220] + (f" errors {errors}" if errors else ""))

    trap = client.get("/api/swaps/cache/trap").json()
    check("cache: the threshold sweep", len(trap["thresholds"]) == len(trap["paraphrases_served"]) == 20 and trap["unservable"] == 26)
    dots = client.get("/api/swaps/consolidation/dots").json()
    check("consolidation: similarity by relation", sorted(len(v) for v in dots["groups"].values()) == [10] * 5)

    hosted = next((m for m in ("jev", "openai") if m in models), models[0])
    run = stream("/api/swaps/routing/run", {"backend": hosted})
    check("routing: the labelled set, live", run["requests"] == 58 and 0 <= run["score"] <= 1, f"{hosted}: {run['detail']}")

    tk = client.get("/api/tokenomics").json()
    check("tokenomics", len(tk["calls"]) >= 8, f"{len(tk['calls'])} calls, ${sum(s['usd'] for s in tk['summary']):.5f}")
    rows = client.get("/api/data_explorer/tables/session_decisions/rows?limit=5").json()
    check("data explorer", rows["total"] >= 8, f"{rows['total']} session rows")

    failed = [n for n, ok, _ in results if not ok]
    print(f"\n{len(results) - len(failed)} of {len(results)} passed" + (f"; failed: {failed}" if failed else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
