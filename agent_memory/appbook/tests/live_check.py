"""Opt-in end-to-end checks against a running app and real OpenAI responses.

Run python tests/live_check.py --live --url http://127.0.0.1:8877.
This creates sessions and incurs API usage. No saved answers or mock providers.
"""

import argparse
import json
import re
import urllib.error
import urllib.request
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--live", action="store_true", required=True)
parser.add_argument("--url", default="http://127.0.0.1:8877")
parser.add_argument("--model", default="gpt-6-astra")
args = parser.parse_args()
results = {}


def api(path, value=None):
    request = urllib.request.Request(args.url + "/api" + path,
                                    data=json.dumps(value).encode() if value is not None else None,
                                    headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=300) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        raise RuntimeError(error.read().decode()) from error


def create(mode, budget=12000, checks=120):
    return api("/sessions", {"mode": mode, "model": args.model, "budget": budget,
                            "notes_budget": 2400, "diagnostic_checks": checks})


def chat(s, prompt):
    return api(f"/sessions/{s['id']}/chat", {"prompt": prompt})


def reduce(s, **kwargs):
    return api(f"/sessions/{s['id']}/reduce", kwargs)


def answer(s):
    return next(m["text"] for m in reversed(s["messages"]) if m["role"] == "assistant")


def tools_since(s, index):
    return [t for t in s["trace"][index:] if t["kind"] == "tool"]


def diagnostic(s):
    return next(t["result"] for t in s["trace"] if t.get("tool") == "read_diagnostic_log")


prompt = ("Mina owns Release Cedar. The retry limit is 4. Run the clock diagnostic once "
          "and briefly explain why the proposed fix failed. Do not repeat its incidental trace_marker.")
marker_question = "What was the exact trace_marker in the original diagnostic result? Never guess."

s = chat(create("summary"), prompt)
marker = diagnostic(s)["trace_marker"]
s = reduce(s)
assert marker not in json.dumps(s["windows"][-1]["items"])
s = chat(s, marker_question)
assert marker not in answer(s)
results["summary"] = {"id": s["id"], "reduction": s["reductions"][-1], "omitted_fact_unavailable": True}
print("PASS summary: intentional omission and measured reduction", flush=True)

s = chat(create("offload"), prompt)
marker = diagnostic(s)["trace_marker"]
s = reduce(s, tool_only=True)
transition = s["reductions"][-1]
assert transition["saved_tokens"] > 0
assert transition["reference"]["tool_call_ids"]
assert not any(i["kind"] in {"function_call", "function_call_output"} for i in s["windows"][-1]["items"])
index = len(s["trace"])
s = chat(s, marker_question)
assert marker in answer(s)
assert "just_in_time_retrieval" in [t["tool"] for t in tools_since(s, index)]
assert "read_diagnostic_log" not in [t["tool"] for t in tools_since(s, index)]
results["offload"] = {"id": s["id"], "reduction": transition, "retrieved_original_marker": True}
print("PASS offload: balanced exchange removed; marker recovered through a real tool", flush=True)

s = chat(create("offload"), "Remember that Mina owns Release Cedar. Reply with one short sentence.")
s = reduce(s)
results["tiny_offload"] = {"id": s["id"], "reduction": s["reductions"][-1]}
print("MEASURE tiny offload:", s["reductions"][-1]["saved_tokens"], "tokens saved (negative is overhead)", flush=True)

s = chat(create("notes"), prompt)
marker = diagnostic(s)["trace_marker"]
s = reduce(s)
first_notes = s["notes"]
assert any(n["kind"] == "failed_fix" for n in first_notes)
assert any(n["kind"] == "component" for n in first_notes)
s = chat(s, "New decision: run staging validation before rollout. Acknowledge briefly.")
s = reduce(s)
assert len(s["windows"]) == 3
assert s["notes"][:len(first_notes)] == first_notes
assert not any(n["kind"] in {"failed_fix", "component"} for n in s["notes"] if n["window_number"] == 2)
assert marker not in json.dumps(s["windows"][-1]["items"])
index = len(s["trace"])
s = chat(s, "Which clock approach failed and why? What retry limit should Mina use?")
assert not tools_since(s, index), "Carried notes should answer this without retrieval."
assert "4" in answer(s) and any(x in answer(s).lower() for x in ["twice", "double", "two times"])
index = len(s["trace"])
s = chat(s, marker_question)
assert marker in answer(s)
searches = [t for t in tools_since(s, index) if t["tool"] == "search_session"]
assert searches and any(hit["window_number"] == 1 and marker in hit["excerpt"] for t in searches for hit in t["result"])
s = chat(s, "Mina's latest update: the retry limit is now 6. What limit applies?")
assert re.search(r"\b6\b", answer(s))
results["notes"] = {"id": s["id"], "windows": len(s["windows"]), "notes": len(s["notes"]),
                    "carried_failure_without_search": True, "w3_searched_w1": True,
                    "latest_user_correction_wins": True, "old_notes_unchanged": True}
print("PASS notes: W1 failure carried to W3, originals searched, latest correction respected", flush=True)

s = create("notes", budget=6000, checks=350)
s = chat(s, "Run the clock diagnostic once. What went wrong and how does the component behave?")
diagnostics = [t for t in s["trace"] if t.get("tool") == "read_diagnostic_log"]
assert len(diagnostics) == 1
assert len(s["reductions"]) == 1 and len(s["windows"]) == 2
assert s["reductions"][0]["automatic"]
assert s["reductions"][0]["trigger_item"] == "function_call_output"
assert "9000" in answer(s).replace(",", "")
results["midloop"] = {"id": s["id"], "diagnostic_calls": 1, "reduction": s["reductions"][0]}
print("PASS mid-loop: diagnostic crosses threshold; one execution, one automatic rotation", flush=True)

out = Path(__file__).resolve().parents[1] / ".data" / "validation"
out.mkdir(parents=True, exist_ok=True)
(out / "live-check.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
print("Live checks passed; inspection session IDs saved to", out / "live-check.json", flush=True)
