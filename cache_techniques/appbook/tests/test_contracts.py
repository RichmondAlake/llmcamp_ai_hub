"""Cache identity, expiry and accounting checks without paid provider requests."""
import copy
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend import service as s
from backend import experiments as e
from backend.main import Config, Features


def test_ttl_expiry_mutation_and_capacity(monkeypatch):
    now = [100.0]
    monkeypatch.setattr(s.c.time, "monotonic", lambda: now[0])
    cache = s.c.TTLCache(ttl_seconds=3, capacity=2)
    original = {"sources": ["a"]}
    cache.put("a", original)
    original["sources"].append("b")
    read = cache.get("a")
    read["sources"].append("c")
    assert cache.get("a") == {"sources": ["a"]}
    cache.put("b", 2)
    cache.put("c", 3)
    assert cache.get("a") is s.c.MISSING
    now[0] = 104
    assert cache.get("b") is s.c.MISSING


@pytest.mark.parametrize("query,expected", [
    ("Explain semantic caching", True), ("Explain workflow memory", True),
    ("What is the current price of an embedding model?", False),
    ("Find flight availability", False), ("Remember my trip", False),
    ("What is my favorite color?", False),
    ("Explain continual learning to me in detail", True), ("What is HNSW?", True),
    ("Explain the latest research on caching", False),
])
def test_answer_reuse_scope(query, expected):
    assert s.eligible(query) is expected


def test_unknown_and_failed_usage_is_not_zero(monkeypatch):
    monkeypatch.setattr(s.c, "CALLS", [])
    monkeypatch.setattr(s.c, "EMBEDDING_CALLS", [])
    monkeypatch.setattr(s.c, "SEARCH_CALLS", [{"estimated_usd": None}])
    assert s.usage((0, 0, 0), 1)["estimated_usd"] is None
    monkeypatch.setattr(s.c, "SEARCH_CALLS", [])
    assert s.usage((0, 0, 0), 1, failed=True)["estimated_usd"] is None
    assert s.usage((0, 0, 0), 1)["estimated_usd"] == 0


def test_live_requests_never_reuse_or_store_answers():
    # Poison answer caches: entering them is an immediate test failure.
    class Poison:
        def get(self, key):
            raise AssertionError("Live research entered an answer cache")
        def put(self, key, value):
            raise AssertionError("Live research stored an answer")
    lane = object.__new__(s.Lane)
    lane.normal, lane.namespace = Poison(), "test"
    lane.features = {"semantic": True}
    lane.service = SimpleNamespace(tavily=None)
    lane.config = {"depth": "basic", "max_results": 1}
    lane.tool = None
    lane.adapter = SimpleNamespace(hits=0)
    lane.generate = lambda query, evidence: "A fresh answer"
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(s.c, "live_tool", lambda *args: {"results": [], "tool_cache_hit": False, "collected_at": 123})
        result = lane.request("Current embedding prices", "live")
    assert result["reuse_eligible"] is False
    assert result["answer"] == "A fresh answer"


def test_namespace_covers_context_options_and_owner():
    core = SimpleNamespace()
    config = Config().model_dump()
    first = s.Lane(core, "owner-a", {}, config)
    for owner, changed in [("owner-b", config), ("owner-a", config | {"revision": "v2"}),
                           ("owner-a", config | {"ttl": 30})]:
        assert first.namespace != s.Lane(core, owner, {}, changed).namespace


def test_custom_count_and_scenario_progression(monkeypatch):
    monkeypatch.setattr(s, "require", lambda: SimpleNamespace(workspace="test"))
    payload = {"mode": "custom", "requests": [{"query": "Explain memory", "kind": "explanation"}], "turns": 2}
    with pytest.raises(ValueError, match="exactly one"):
        e.prepare(payload)
    varied = e.preset("diverse", 30, "unused")
    assert len(set(row["query"] for row in varied)) == 30
    mixed = e.preset("mixed", 6, "live request")
    assert mixed[0] == mixed[1] and mixed[4] == mixed[5]
    assert [row["kind"] for row in mixed[-2:]] == ["live", "live"]
    invalidated = e.preset("invalidation", 3, "unused")
    assert len({r["revision"] for r in invalidated}) == 3


def test_cumulative_and_individual_stacks():
    cumulative = e.stages("cumulative", {})
    assert len(cumulative) == 6
    for i, (_, _, features) in enumerate(cumulative):
        assert sum(features.values()) == i
    individual = e.stages("individual", {})
    assert all(sum(f.values()) == 1 for _, _, f in individual[1:])
    custom = {name: name == "tool" for name in s.FEATURES}
    assert e.stages("custom", custom)[1][2] == custom


def test_unknown_cache_options_are_rejected():
    with pytest.raises(ValueError):
        Features(normal=True, invented_cache=True)
    with pytest.raises(ValueError):
        Config(ttl=-1)


def test_multiple_cache_hits_are_distinct():
    result = {"hit": "tool", "embedding_hits": 2, "metrics": {"cache_read_tokens": 800}}
    s.annotate_hits(result)
    assert result["cache_hits"] == ["tool", "embedding", "prompt"]


def test_interrupted_job_keeps_partial_measurements(monkeypatch, tmp_path):
    monkeypatch.setattr(e, "DATA", tmp_path)
    monkeypatch.setattr(e, "jobs", {})
    monkeypatch.setattr(s, "require", lambda: SimpleNamespace(workspace="scope"))
    job = {"id": "a" * 32, "workspace": "scope", "status": "running", "rows": [{"turn": 1}], "current": {"turn": 2}}
    e.persist(job)
    restored = e.get(job["id"])
    assert restored["status"] == "interrupted"
    assert restored["rows"] == job["rows"]
    assert restored["current"] is None


def test_revision_initialization_is_measured(monkeypatch, tmp_path):
    """A revised semantic cache can call an encoder during construction."""
    monkeypatch.setattr(e, "DATA", tmp_path)
    monkeypatch.setattr(s, "require", lambda: SimpleNamespace(workspace="scope"))
    monkeypatch.setattr(s.c, "CALLS", [])
    monkeypatch.setattr(s.c, "EMBEDDING_CALLS", [])
    monkeypatch.setattr(s.c, "SEARCH_CALLS", [])
    class MeteredLane:
        def __init__(self, core, owner, features, config):
            self.owner, self.features, self.config = owner, features, config
            s.c.EMBEDDING_CALLS.append({"input_tokens": 10, "estimated_usd": 0.001})
        def request(self, query, kind):
            return {"answer": "test", "hit": None}
    monkeypatch.setattr(s, "Lane", MeteredLane)
    job = {"id": "b" * 32, "workspace": "scope", "lanes": [{"id": "test", "features": {}}],
           "config": {"revision": "v1"}, "setup": {}, "rows": [], "cancel_requested": False,
           "workload": {"requests": [{"query": "Explain memory", "kind": "explanation", "revision": "v2"}]}}
    e.worker(job)
    assert job["status"] == "completed"
    assert job["setup"]["test"]["estimated_usd"] == 0.001
    assert job["rows"][0]["estimated_usd"] == 0.001


def test_true_cache_reads_fall_back_to_the_primary(monkeypatch):
    rows = {"replica": [], "primary": [{"payload": '{"answer": "saved"}'}]}
    monkeypatch.setattr(s.c, "sql_rows", lambda conn, sql, binds: rows[conn])
    store = s.c.TrueCacheStore("primary", "replica", ttl_seconds=60)
    assert store.get("key") == {"answer": "saved"} and store.last_tier == "primary"
    rows["replica"] = rows["primary"]
    assert store.get("key") == {"answer": "saved"} and store.last_tier == "true_cache"
    rows["replica"], rows["primary"] = [], []
    assert store.get("key") is s.c.MISSING and store.last_tier is None


def test_vector_space_verdict_walks_candidates_like_a_lookup(monkeypatch):
    monkeypatch.setattr(s.c, "rerank", lambda query, texts: [-1.0, 2.0, 5.0][:len(texts)])
    core = object.__new__(s.Service)
    ranked = [{"text": "a", "kind": "cached", "cosine_distance": 0.05},
              {"text": "b", "kind": "example", "cosine_distance": 0.08},
              {"text": "c", "kind": "cached", "cosine_distance": 0.5}]
    vetoed_then_accepted = core.verdict("q", copy.deepcopy(ranked), threshold=0.1, rerank_min=0.0)
    assert vetoed_then_accepted["hit"] and vetoed_then_accepted["matched"]["text"] == "b"
    assert [c["outcome"] for c in vetoed_then_accepted["checked"]] == ["vetoed by the reranker", "accepted"]
    too_far = core.verdict("q", copy.deepcopy(ranked), threshold=0.04, rerank_min=0.0)
    assert not too_far["hit"] and [c["outcome"] for c in too_far["checked"]] == ["too far"]
    expired_only = core.verdict("q", [{"text": "x", "kind": "expired", "cosine_distance": 0.0}], 0.1, 0.0)
    assert not expired_only["hit"] and expired_only["checked"] == []


def test_explorer_summarises_vectors_and_only_serves_known_tables():
    import array
    summary = s.readable(array.array("f", [3.0, 4.0] + [0.0] * 382))
    assert summary["vector"] == "VECTOR(384, FLOAT32)" and summary["norm"] == 5.0
    assert s.readable(b"\x01\xff") == "01ff"
    assert set(s.EXPLORER) == {s.c.RESPONSE_TABLE, s.c.SEMANTIC_TABLE, s.SEM_TABLE, s.NOTES_TABLE, s.EXAMPLES_TABLE}
    assert s.EXPLORER[s.c.RESPONSE_TABLE][1] == "true_cache"
