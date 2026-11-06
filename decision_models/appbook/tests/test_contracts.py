"""Offline contracts: routes, schemas, the explorer allowlist, the swap pages, and no keys in replies.

No model is called: the decision backends are replaced by a fake that answers in d1's shape, and the
typical paths (which need OpenAI embeddings) are switched off.
    ../.venv/bin/python -m pytest tests/test_contracts.py -q
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from pathlib import Path

import numpy as np
import pytest

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))

from fastapi.testclient import TestClient  # noqa: E402

from backend.core import explorer, models, session  # noqa: E402
from backend.core.swaps import BY_ID, common, reranking, tools  # noqa: E402
from backend.main import app  # noqa: E402

client = TestClient(app)
SWAP_IDS = ["chunking", "reranking", "cache", "routing", "consolidation", "extraction", "tools"]


def fake_answers(questions: dict) -> dict:
    out = {}
    for name, q in questions.items():
        if q["type"] == "noul":
            out[name] = {"type": "noul", "noul": 0.9}
        elif q["type"] == "choice":
            keys = list(q["criteria"])
            probs = {k: (0.7 if i == 0 else 0.3 / (len(keys) - 1)) for i, k in enumerate(keys)}
            out[name] = {"type": "choice", "choice": keys[0], "confidence": 0.7, "probabilities": probs}
        else:
            out[name] = {"type": "score", "score": 1.0, "confidence": 0.5, "legend": {"0": "a", "1": "b"},
                         "probabilities": {"0": 0.2, "1": 0.8}}
    return out


def fake_embed(texts):
    out = []
    for t in texts:
        rng = np.random.default_rng(int(hashlib.sha1(t.encode()).hexdigest()[:8], 16))
        v = rng.normal(size=16)
        out.append(v / np.linalg.norm(v))
    return np.array(out)


@pytest.fixture()
def fake_models(monkeypatch):
    monkeypatch.setattr(models, "_call", lambda name, state, questions: (fake_answers(questions), 100, None))
    monkeypatch.setattr(models, "available", lambda name: True)
    monkeypatch.setattr(models, "load_local", lambda: None)
    monkeypatch.setattr(models.d1, "model", lambda: type("M", (), {
        "system_one_batch": staticmethod(lambda batch: [{"answers": fake_answers(q), "usage": {"input_tokens": 10}} for _, q in batch])})())
    monkeypatch.setattr(common, "openai_ready", lambda: False)
    monkeypatch.setattr(common, "embed", fake_embed)
    monkeypatch.setattr(tools, "top_k", lambda session, turn, k: ["send_email", "generate_report", "post_to_slack", "get_weather", "lookup_order"][:k])
    monkeypatch.setattr(reranking, "cross_encoder", lambda: type("CE", (), {"predict": staticmethod(lambda pairs: [0.0] * len(pairs))})())
    yield


# ── the shell ─────────────────────────────────────────────────────────
def test_frontend_files_are_served_and_linked():
    html = (APP / "frontend" / "index.html").read_text()
    for name in ("styles.css", "decide.css", "app.js", "charts.js", "architecture.js", "pages.js", "results.js"):
        assert f"/{name}" in html and (APP / "frontend" / name).exists()
        assert client.get(f"/{name}").status_code == 200


@pytest.mark.parametrize("url", ["/api/health", "/api/architecture", "/api/swaps", "/api/evidence/scoreboard",
                                 "/api/evidence/providers", "/api/tokenomics", "/api/session", "/api/data_explorer/tables",
                                 "/api/data_explorer/activity", *[f"/api/swaps/{s}" for s in SWAP_IDS]])
def test_read_routes_answer(url):
    assert client.get(url).status_code == 200


def test_no_key_value_reaches_a_reply():
    keys = [os.environ.get(k) for k in ("OPENAI_API_KEY", "TYPESAFE_API_KEY", "LIQUID_API_KEY", "HF_TOKEN")]
    body = "".join(client.get(u).text for u in ("/api/health", "/api/architecture", "/api/swaps", "/api/session",
                                                "/api/data_explorer/tables"))
    for key in filter(None, keys):
        assert key not in body


def test_every_swap_and_measure_page_is_in_the_nav_and_the_router():
    app_js = (APP / "frontend" / "app.js").read_text()
    for page in SWAP_IDS + ["scoreboard", "providers", "tokenomics"]:
        assert f'href: "#/{page}"' in app_js
    assert 'const SWAP_IDS = ["chunking", "reranking", "cache", "routing", "consolidation", "extraction", "tools"]' in app_js
    for page in ("scoreboard", "providers", "tokenomics"):
        assert f"{page}: view" in app_js


def test_frontend_text_has_no_session_wording():
    banned = re.compile(r"\b(webinar|workshop|lesson|lecture|slides?)\b", re.I)
    for path in (APP / "frontend").glob("*.js"):
        assert not banned.search(path.read_text()), path.name
    assert not banned.search((APP / "frontend" / "index.html").read_text())
    for module in BY_ID.values():
        assert not banned.search(json.dumps(module.META)), module.META["id"]


# ── the seven swaps, the architecture, the evidence ───────────────────
def test_the_seven_swaps_are_in_notebook_order_and_complete():
    d = client.get("/api/swaps").json()["swaps"]
    assert [s["id"] for s in d] == SWAP_IDS and [s["n"] for s in d] == list(range(1, 8))
    for s in d:
        assert s["today"] and s["today_short"] and s["model"] and s["judge"] and s["when"] and s["subtitle"]
        assert len(s["examples"]) >= 1 and len(s["takeaways"]) >= 3
        assert s["notebook"].startswith(f"0{s['n']}_")


def test_the_notebooks_explanations_are_on_their_pages():
    swaps = {s["id"]: s for s in client.get("/api/swaps").json()["swaps"]}
    titles = {sid: [n["title"] for n in s.get("notes", [])] for sid, s in swaps.items()}
    assert "What a gap is" in titles["chunking"]
    assert "Why one yes-or-no per store, and not one Choice" in titles["routing"]
    assert any("Who does what" in t for t in titles["reranking"]) and any("Who does what" in t for t in titles["tools"])
    assert swaps["reranking"]["question"]["0"]["type"] == "noul"
    for s in swaps.values():
        for n in s.get("notes", []):
            assert all(len(r) == len(n["columns"]) for r in n.get("rows", []))


def test_every_swap_has_its_notebook_scorecard():
    for s in client.get("/api/swaps").json()["swaps"]:
        card = s["scorecard"]
        assert card, f"run notebooks/{s['notebook']}.ipynb"
        assert card["verdict"] in ("better", "level", "worse")
        assert 0 <= card["today"] <= 1 and 0 <= card["model"] <= 1 and card["n"] >= 40


def test_architecture_places_all_twenty_points_and_the_cache():
    d = client.get("/api/architecture").json()
    assert [p["n"] for p in d["points"]] == list(range(1, 21))
    assert {s["name"] for s in d["stages"]} == {"Retain", "Refine", "Recall", "Reuse"}
    built = [p for p in d["points"] if p["status"] == "built"]
    assert d["built"] == len(built) == 11
    assert all(p["page"] in SWAP_IDS and p["swap"] for p in built)
    assert d["extra"]["page"] == "cache" and [s["id"] for s in d["swaps"]] == SWAP_IDS


# ── the Data Explorer ─────────────────────────────────────────────────
def test_explorer_is_allowlisted_and_capped():
    assert client.get("/api/data_explorer/tables/users/rows").status_code == 404
    assert client.get("/api/data_explorer/tables/labels_tools/rows?limit=1000").status_code == 422
    assert client.get("/api/data_explorer/tables/labels_tools/rows?scope=everything").status_code == 422
    d = client.get("/api/data_explorer/tables/labels_memory_routing/rows?limit=5").json()
    assert d["total"] == 58 and len(d["rows"]) == 5
    assert client.get("/api/data_explorer/tables/labels_tools/rows").json()["total"] == 75


def test_explorer_never_sends_vectors_or_long_text():
    for name in explorer.TABLES:
        d = client.get(f"/api/data_explorer/tables/{name}/rows?scope=all&limit=20").json()
        assert not set(d["columns"]) & {"embedding", "embeddings", "vector", "vectors"}
        for row in d["rows"]:
            for v in row.values():
                assert not (isinstance(v, str) and len(v) > 301)
                assert not isinstance(v, list)


# ── request schemas ───────────────────────────────────────────────────
@pytest.mark.parametrize("body", [
    {"state": "x", "questions": [{"name": "Bad Name", "type": "noul", "instructions": "?"}]},
    {"state": "x", "questions": [{"name": "c", "type": "choice", "instructions": "?", "options": {"a": "only one"}}]},
    {"state": "x", "questions": [{"name": f"q{i}", "type": "noul", "instructions": "?"} for i in range(9)]},
    {"state": "x" * 5000, "questions": [{"name": "q", "type": "noul", "instructions": "?"}]},
    {"state": "x", "questions": [{"name": "q", "type": "noul", "instructions": "?"}], "backends": ["gpt-5"]},
])
def test_playground_rejects_bad_requests(body):
    assert client.post("/api/playground", json=body).status_code == 422


def test_try_rejects_bad_input():
    assert client.post("/api/swaps/nothing/try", json={"text": "x"}).status_code == 404
    assert client.post("/api/swaps/routing/try", json={"text": "x" * 5000}).status_code == 422
    assert client.post("/api/swaps/routing/try", json={"text": "  "}).status_code == 422
    assert client.post("/api/swaps/consolidation/try", json={"stored": "a"}).status_code == 422
    assert client.post("/api/swaps/routing/run", json={"backend": "gpt-5"}).status_code == 422


# ── the swaps, with fake models ───────────────────────────────────────
@pytest.mark.parametrize("swap_id", SWAP_IDS)
def test_every_swap_answers_its_first_example_with_every_model(fake_models, swap_id):
    example = client.get(f"/api/swaps/{swap_id}").json()["examples"][0]["input"]
    body = {"backends": ["local", "jev", "openai"], **(example if isinstance(example, dict) else {"text": example})}
    before = len(session.current().calls)
    d = client.post(f"/api/swaps/{swap_id}/try", json=body).json()
    by_key = {m["key"]: m for m in d["methods"]}
    assert {"local", "jev", "openai"} <= set(by_key)
    for k in ("local", "jev", "openai"):
        assert by_key[k]["answer"] and "error" not in by_key[k] and by_key[k]["request"]
    assert len(session.current().calls) == before + 1
    assert set(client.get("/api/session").json()["last"]["calls"]) == {"local", "jev", "openai"}


def test_routing_reads_every_yes_as_a_store(fake_models):
    d = client.post("/api/swaps/routing/try", json={"text": "Book the same restaurant as last time; I'm vegetarian now.",
                                                     "backends": ["jev"]}).json()
    jev = next(m for m in d["methods"] if m["key"] == "jev")
    assert jev["answer"] == "episodic + semantic + procedural" and jev["right"] is False
    assert d["truth"] == "Needs: episodic + semantic"


def test_consolidation_maps_the_relation_to_its_action(fake_models):
    d = client.post("/api/swaps/consolidation/try", json={"stored": "The user lives in London.",
                                                           "new": "The user moved out of London and now lives in Leeds.",
                                                           "backends": ["openai"]}).json()
    m = next(m for m in d["methods"] if m["key"] == "openai")
    assert m["answer"] == "same → skip" and m["right"] is False and d["truth"] == "Labelled: contradicts → supersede"


def test_openai_request_is_translated():
    view = models.request_view("openai", {"k": "v"}, {"q": {"type": "noul", "instructions": "ok?", "criteria": {"true": "y", "false": "n"}}})
    assert view["model"] == "gpt-6-luna" and view["input"][0]["content"][0]["type"] == "input_json"
    assert view["questions"][0]["type"] == "predicate" and "True when: y" in view["questions"][0]["instructions"]
    assert models.request_view("jev", "s", {"q": {}})["state"] == "s"


def test_label_set_runs_stream_a_scored_result(fake_models):
    r = client.post("/api/swaps/routing/run", json={"backend": "jev"})
    assert r.status_code == 200
    lines = r.text.replace("\r\n", "\n").split("\n")
    events = [line.split(":", 1)[1].strip() for line in lines if line.startswith("event:")]
    assert "progress" in events and events[-1] == "result"
    result = json.loads([line[5:].strip() for line in lines if line.startswith("data:")][-1])
    assert result["measure"] == "right route" and result["requests"] == 58 and 0 <= result["score"] <= 1
    assert result["notebook"]["verdict"] in ("better", "level", "worse")


def test_reset_starts_a_new_session_and_keeps_the_old_log():
    old = client.get("/api/session").json()["id"]
    new = client.post("/api/session/reset").json()
    assert new["id"] != old and new["kept"] is True
