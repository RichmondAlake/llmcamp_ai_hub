"""Opt-in live validation; bills the configured providers and writes observed evidence."""
import json
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "tests/artifacts"
ARTIFACTS.mkdir(parents=True, exist_ok=True)
client = httpx.Client(base_url="http://localhost:8033", timeout=180)
report = {"pairs": {}, "checks": []}


def api(path, payload=None):
    response = client.get(path) if payload is None else client.post(path, json=payload)
    response.raise_for_status()
    return response.json()


def record(name, result):
    report["pairs"][name] = {side: {key: value for key, value in result[side].items() if key != "vector"} for side in ["without", "with"]}
    report["pairs"][name].update(namespace=result["namespace"], savings=result["savings"], setup=result["setup"])
    (ARTIFACTS / "live_api.json").write_text(json.dumps(report, indent=2))
    print(name, result["with"]["status"], result["with"]["hit"], result["with"]["metrics"]["estimated_usd"], flush=True)


def compare(mechanism, query, **kwargs):
    result = api("/api/compare/" + mechanism, {"query": query, **kwargs})
    assert result["without"]["status"] == "success", result["without"]["error"]
    assert result["with"]["status"] == "success", result["with"]["error"]
    for side in ["without", "with"]:
        m = result[side]["metrics"]
        assert m["processed_input_tokens"] == m["input_tokens"] + m["cache_write_tokens"] + m["cache_read_tokens"]
        assert m["estimated_usd"] is not None
    return result


def main():
    assert api("/api/status")["ready"]
    queries = {
        "normal": "Explain why an exact response cache needs a TTL.",
        "embedding": "A semantic cache retrieves previously generated answers.",
        "semantic": "Explain how semantic caching helps agent memory.",
        "prompt": "Explain embedding caching in two sentences.",
        "tool": "Oracle AI Database HNSW vector search official documentation",
        "unified": "Explain how semantic caching helps agent memory.",
    }
    for mechanism, query in queries.items():
        api("/api/reset/" + mechanism, {})
        first = compare(mechanism, query)
        record(mechanism + "-cold", first)
        assert not {"normal", "semantic", "tool", "prompt"}.intersection(first["with"].get("cache_hits", []))
        second = compare(mechanism, query)
        record(mechanism + "-warm", second)
        expected = "normal" if mechanism == "unified" else mechanism
        assert second["with"]["hit"] == expected
        if mechanism in ["normal", "unified"]:
            assert second["with"]["metrics"]["provider_calls"] == 0
            assert second["with"]["metrics"]["estimated_usd"] == 0
        if mechanism == "embedding":
            assert first["with"]["vector"] == second["with"]["vector"]
            assert second["with"]["metrics"]["embedding_calls"] == 0
            role = compare(mechanism, query, role="query")
            record("embedding-role-miss", role)
            assert role["with"]["hit"] is None
        if mechanism == "semantic":
            assert second["with"]["metrics"]["provider_calls"] == 0
            assert abs(second["with"]["distance"]) < 1e-4
            paraphrase = compare(mechanism, "How can a semantic cache help an agent reuse an earlier answer?")
            record("semantic-paraphrase", paraphrase)
        if mechanism == "prompt":
            assert first["with"]["metrics"]["cache_write_tokens"] >= 512
            assert second["with"]["metrics"]["cache_read_tokens"] >= 512
            assert second["with"]["metrics"]["provider_calls"] == 1
        if mechanism == "tool":
            assert second["with"]["metrics"]["tool_calls"] == 0
            assert second["with"]["metrics"]["provider_calls"] == 1
            assert second["with"]["collected_at"] == first["with"]["collected_at"]
    revised = compare("normal", queries["normal"], config={"revision": "v2"})
    record("source-revision-miss", revised)
    assert revised["with"]["hit"] is None
    expired = compare("normal", "Explain memory cache expiry.", config={"ttl": 0.1})
    again = compare("normal", "Explain memory cache expiry.", config={"ttl": 0.1})
    record("normal-expiry-miss", again)
    assert again["with"]["hit"] is None
    off = compare("unified", queries["unified"], config={"features": {name: False for name in queries if name != "unified"}})
    record("unified-all-off", off)
    assert off["with"]["metrics"]["provider_calls"] == 1
    assert off["with"]["hit"] is None
    response = client.post("/api/compare/normal", json={"query": "test", "config": {"features": {"unsupported": True}}})
    assert response.status_code == 422
    assert client.post("/api/sandbox", json={}, headers={"Origin": "https://example.com"}).status_code == 403
    assert client.get("/api/tokenomics/" + "a" * 32).status_code == 404
    report["checks"] += ["all six live paired paths", "cold/warm hits", "provider token accounting", "role isolation", "context invalidation", "TTL expiry", "all-off stack", "unknown options rejected", "cross-origin writes rejected", "missing job 404"]
    (ARTIFACTS / "live_api.json").write_text(json.dumps(report, indent=2))
    print("Live paired validation passed", flush=True)


if __name__ == "__main__":
    main()
