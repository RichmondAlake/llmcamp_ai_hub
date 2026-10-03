"""Reviewed workloads, independently cold cache lanes and live cost accounting."""
import copy
import json
import threading
import time
import uuid
from pathlib import Path

from . import service as s

DATA = Path(__file__).resolve().parents[1] / "data/jobs"
jobs = {}
job_lock = threading.RLock()
LABELS = {"baseline": "Baseline", "normal": "Normal cache", "embedding": "Embedding cache",
          "semantic": "Semantic cache", "prompt": "Prompt cache", "tool": "Tool cache", "custom": "Custom stack"}
COLORS = ["#ffcc66", "#b7ff5a", "#52e2bd", "#93bbff", "#ad9bff", "#ff9db7", "#efbdff"]
TOPICS = ["exact response caching", "semantic caching", "embedding caching", "provider prompt caching",
          "tool-result caching", "HNSW retrieval", "context engineering", "workflow memory"]


def preset(scenario, turns, live_query):
    if scenario == "repeat":
        queries = ["Explain how semantic caching helps agent memory in two sentences.",
                   "Explain how semantic caching helps agent memory in two sentences.",
                   "How does a semantic cache help an agent reuse a previous answer?",
                   "Explain embedding caching in two sentences."]
        return [{"query": queries[i % len(queries)], "kind": "explanation"} for i in range(turns)]
    if scenario == "mixed":
        sequence = preset("repeat", 4, live_query) + [{"query": live_query, "kind": "live"}] * 2
        return [copy.deepcopy(sequence[i % len(sequence)]) for i in range(turns)]
    return [{"query": f"Explain {TOPICS[i % len(TOPICS)]}, focusing on {['cache identity', 'expiry', 'measured cost', 'context selection'][i // len(TOPICS)]}. Keep it brief.",
             "kind": "explanation", **({"revision": f"revision-{i+1}"} if scenario == "invalidation" else {})}
            for i in range(turns)]


def prepare(payload):
    core = s.require()
    generation = None
    if payload["mode"] == "custom":
        requests = payload["requests"]
        if len(requests) != payload["turns"]:
            raise ValueError("Provide exactly one request per turn; custom inputs never silently repeat")
    elif payload["mode"] == "synthetic":
        prompt = (f"Generate exactly {payload['turns']} short user requests about caching and agent memory. "
                  "Make them evolve: include exact repeats and close paraphrases to exercise caching, plus different concepts. "
                  "Return only a JSON object with a requests array; each item has query (string) and kind (explanation). "
                  f"Focus: {payload['focus'] or 'cache usage and context engineering'}")
        result = s.measure("workload:" + core.workspace, lambda: {"answer": s.c.generate(core.client, prompt,
                            "Generate a reviewable workload. Return valid JSON without Markdown fences.")})
        if result["status"] != "success":
            raise RuntimeError(result["error"])
        text = result["answer"].strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0]
        requests = json.loads(text)["requests"]
        generation = result["metrics"]
    else:
        requests = preset(payload["scenario"], payload["turns"], payload["live_query"])
    if len(requests) != payload["turns"] or any(
        not isinstance(row, dict) or row.get("kind") not in {"explanation", "live"}
        or not isinstance(row.get("query"), str) or not 0 < len(row["query"].strip()) <= 4000 for row in requests
    ):
        raise ValueError("Workload needs the requested count of nonempty, typed requests")
    return {"requests": requests, "generation": generation, "workspace": core.workspace,
            "id": uuid.uuid4().hex, "mode": payload["mode"], "scenario": payload["scenario"]}


def stages(mode, features):
    off = {name: False for name in s.FEATURES}
    result = [("baseline", "Baseline", off)]
    if mode == "custom":
        return result + [("custom", "Custom stack", features)]
    if mode == "individual":
        return result + [(name, LABELS[name], off | {name: True}) for name in s.FEATURES]
    return result + [("stage" + str(i+1), " + ".join(s.FEATURES[:i+1]),
                       {name: j <= i for j, name in enumerate(s.FEATURES)}) for i in range(len(s.FEATURES))]


def persist(job):
    DATA.mkdir(exist_ok=True, parents=True)
    path = DATA / (job["id"] + ".json")
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(job, indent=2, default=str))
    temp.chmod(0o600)
    temp.replace(path)


def get(job_id):
    with job_lock:
        job = copy.deepcopy(jobs[job_id]) if job_id in jobs else json.loads((DATA / (job_id + ".json")).read_text())
        if job_id not in jobs and job["status"] == "running":
            job.update(status="interrupted", current=None, error="The server restarted before this run finished. Completed measurements are preserved.")
            persist(job)
    if job["workspace"] != s.require().workspace:
        raise ValueError("This experiment belongs to a different cache sandbox")
    return job


def active():
    with job_lock:
        return any(job["status"] == "running" for job in jobs.values())


def recent():
    workspace = s.require().workspace
    result = []
    for path in sorted(DATA.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        job = get(path.stem) if path.stem in jobs else json.loads(path.read_text())
        if job["workspace"] != workspace:
            continue
        if job["status"] == "running" and job["id"] not in jobs:
            job = get(job["id"])
        result.append({"id": job["id"], "status": job["status"], "created_at": job["created_at"],
                       "turns": len(job["workload"]["requests"]), "lanes": len(job["lanes"]), "rows": len(job["rows"]),
                       "mode": job["workload"]["mode"], "scenario": job["workload"]["scenario"]})
        if len(result) == 20:
            break
    return result


def worker(job):
    core = s.require()
    lanes = {}
    try:
        for spec in job["lanes"]:
            owner = f"experiment:{job['id']}:{spec['id']}"
            config = copy.deepcopy(job["config"])
            result = s.measure(owner, lambda spec=spec, config=config: lanes.setdefault(spec["id"], s.Lane(core, owner, spec["features"], config)) and {})
            if result["status"] != "success":
                raise RuntimeError(result["error"])
            job["setup"][spec["id"]] = result["metrics"]
            persist(job)
        for i, request in enumerate(job["workload"]["requests"]):
            order = list(lanes)
            order = order[i % len(order):] + order[:i % len(order)]
            for lane_id in order:
                if job["cancel_requested"]:
                    break
                lane = lanes[lane_id]
                job["current"] = {"lane": lane_id, "turn": i+1}
                # A changed source/prefix revision invalidates every response and provider namespace.
                def operation():
                    selected = lane
                    if request.get("revision") and request["revision"] != lane.config["revision"]:
                        config = lane.config | {"revision": request["revision"]}
                        selected = s.Lane(core, lane.owner, lane.features, config)
                        lanes[lane_id] = selected
                    return selected.request(request["query"], request["kind"])
                # Include revision-triggered cache initialization in this turn's cost.
                result = s.measure(lane.owner, operation)
                s.annotate_hits(result)
                with job_lock:
                    job["rows"].append({"lane": lane_id, "turn": i+1, "request": request,
                                        **result, **result["metrics"]})
                    persist(job)
            if job["cancel_requested"]:
                break
        job["status"] = "cancelled" if job["cancel_requested"] else "completed"
    except Exception as exc:
        job["status"], job["error"] = "failed", s.scrub(exc)
    finally:
        job["current"] = None
        persist(job)


def start(payload):
    core = s.require()
    if active():
        raise ValueError("An experiment is running. Stop it or let it complete")
    workload = payload["workload"]
    if workload["workspace"] != core.workspace:
        raise ValueError("Preview a workload in this cache sandbox first")
    specs = stages(payload["comparison"], payload["config"]["features"])
    job = {"id": uuid.uuid4().hex, "workspace": core.workspace, "status": "running", "created_at": time.time(),
           "lanes": [{"id": name, "label": label, "features": features, "color": COLORS[i]} for i, (name, label, features) in enumerate(specs)],
           "workload": workload, "config": payload["config"], "rows": [], "setup": {}, "current": None,
           "cancel_requested": False, "error": None, "pricing_date": s.c.PRICE_DATE}
    with job_lock:
        jobs[job["id"]] = job
        persist(job)
    threading.Thread(target=worker, args=(job,), daemon=True).start()
    return copy.deepcopy(job)
