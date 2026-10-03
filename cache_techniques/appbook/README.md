# Cachecraft appbook

A live interface for the five cache lessons and their combined stack. Each technique compares the same request with and without that cache. There are no notebook or source-code panels in the interface.

Open **http://localhost:8033** when the server is running. The existing travel appbook on port 8031 is independent.

## Run

```bash
cd cache_techniques/appbook   # from the repository root
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python provision_local.py --container acme-oracle-free
.venv/bin/python provision_true_cache.py --container pri-db-free
.venv/bin/python server.py --port 8033 --ask-keys
```

`provision_local.py` uses the existing `acme-oracle-free` Docker container and creates an independent, minimally privileged schema for the vector features. `provision_true_cache.py` creates an application user on the Oracle True Cache primary (set up as described in the [main README](../README.md#oracle-true-cache-setup-docker)) and saves `data/true_cache.json` with mode 0600: the normal cache writes to the primary (`127.0.0.1:1525/FREEPDB1`) and reads through True Cache (`127.0.0.1:1526/sales_pdb_tc`). Its local connection file is ignored by Git and has mode 0600. With another Oracle AI Database, supply `ORACLE_USER`, `ORACLE_PASSWORD` and `ORACLE_DSN` for a dedicated schema instead. The schema needs VECTOR/HNSW support, CREATE TABLE/SEQUENCE privileges and tablespace quota. Do not use SYS or SYSTEM as the app connection.

The launcher requests Anthropic and Tavily keys with hidden prompts. Embeddings and reranking run locally with open-source Hugging Face models (`sentence-transformers/all-MiniLM-L6-v2`, 384 dimensions, and `cross-encoder/ms-marco-MiniLM-L-6-v2`, both pinned), so no embedding key is needed; the first start downloads them. It also accepts `--env-file /path/to/private/.env` or inherited provider environment variables. Only provider keys are read from that file; the dedicated app schema remains separate. The app binds to loopback, rejects cross-origin writes and does not send credentials to the browser.

## Interfaces

| Interface | What it measures |
|---|---|
| Normal cache | Exact stable answer reuse in an Oracle table: written on the primary, read through Oracle True Cache with a primary fallback; model/source/owner identity and TTL |
| Embedding cache | Local MiniLM vectors, all 384 dimensions, model/revision/input-role identity and avoided encoder runs |
| Semantic cache | Raw Oracle vector SQL, HNSW lookup, actual cosine distance plus a local reranker check, scoped answer reuse and expiry. A 3D vector-space viewer plots the cached questions and your own example questions, places any question you type among them, applies the cache policy to give a hit or miss verdict, and animates the 384-dimension cosine calculation |
| Prompt cache | Raw Anthropic calls, stable prefix inspection and provider-reported cache writes/reads |
| Tool cache | Live Tavily sources, reported credits, identical search argument reuse and preserved collection time |
| Unified stack | Selectable five-layer stack, OracleVS retrieval reranked locally, and OracleSemanticCache from langchain-oracledb |
| Tokenomics | Baseline versus individual, cumulative or custom stacks; reviewed scenarios, synthetic inputs or exact custom sequences |
| Reference architecture | Selectable technique/stack topology, component inspection and cold/warm/expired path simulations; from the unified stack, each mechanism can be played in isolation as a "miss, then hit" run |

A read-only **data explorer** sits under every page: it lists the cache tables (the exact answer cache is read through Oracle True Cache), shows their newest rows with vectors summarised, and opens any row in an inspector. Example questions added in the vector-space viewer are embedded locally, stored per sandbox in `CT_VECTOR_EXAMPLES`, and never call a model.

Architecture simulations do not call providers. The paired interfaces and Tokenomics use real providers, with no canned model outputs or simulated usage. The stable retrieval corpus contains eight authored educational passages; it does not seed personal user memories.

Answer reuse applies to requests marked as stable questions. A stable question that asks about current facts ("today", "latest", prices, availability) or about the user's own state ("my …") is still answered fresh, and the trace says why. Live web research bypasses answer caches and generates a fresh answer, even when a tool response or provider prefix is cached. Semantic distance alone does not prove equivalent intent: the interface exposes the selected match, its distance and reranker score, and the threshold. The default maximum distance is a conservative 0.10 for MiniLM, because different teaching topics (for example "exact response caching" and "semantic caching" in otherwise identical sentences) sit only about 0.18 apart; a real paraphrase here is about 0.29 away and needs an explicitly wider threshold.

Tokenomics freezes one reviewed workload for every lane, starts independent application caches and rotates execution order. A cumulative run adds exact, embedding, semantic, prompt and tool caching sequentially. Synthetic generation is a separately reported shared cost. Each lane's setup and every measured turn contribute to its API estimate. Expiry/context changes can make caching slower or more expensive; savings retain their sign. Cache-hit requests can still include other paid calls, and a cold combined request can reuse an embedding within that same request.

Charts show request latency, cumulative estimated API cost, processed Claude input and provider-reported cached input. Click configuration names to hide/restore their series across all charts. Inspect individual outputs/usage and export full JSON measurements. Saved experiments can be selected after page or server restarts. Stop finishes the current provider request and preserves completed measurements.

The app uses the reviewed provider helpers in `../cache_course.py`. It imports neither notebook builders nor Memorizz source. Dependencies are installed in the app's own environment. `requirements.lock.txt` records the validated versions.

## Validation

```bash
.venv/bin/python -m pytest tests/test_contracts.py -q
.venv/bin/python tests/live_api.py
.venv/bin/python tests/interface_e2e.py
```

The last two commands bill the configured live providers and require the running server. The browser test uses Chromium; set `CACHE_CHROME_PATH` to your installed executable if it differs from the local reference installation. Set `CACHE_APP_URL` to test another local port. The live and browser tests write their evidence (measurements, exported experiments and desktop/mobile screenshots) to `tests/artifacts/`, which is not committed.

Private local connection data, cache namespaces, comparison history and experiment files live under ignored `data/`. In-process embedding and tool TTL caches start empty after a process restart; exact answers in the True Cache table, scoped Oracle semantic records and eligible provider prefixes can remain warm until expiry. New sandbox selects fresh namespaces without deleting shared reference data.

Estimates use API-reported usage and list prices checked on 2026-10-03. Local encoder and reranker runs have no API cost; their compute time is part of measured latency. Unknown provider usage or failed requests have unknown total cost, with known counters preserved. Estimates exclude database/CPU costs, discounts and free credits. Short classroom trials are illustrative measurements, not controlled production benchmarks.

Provider/reference documentation: [Anthropic prompt caching](https://platform.claude.com/docs/en/build-with-claude/prompt-caching), [Oracle True Cache](https://docs.oracle.com/en/database/oracle/oracle-database/23/odbtc/), [Tavily credits](https://docs.tavily.com/documentation/api-credits), [Oracle integration](https://github.com/oracle/langchain-oracle/tree/main/libs/oracledb).
