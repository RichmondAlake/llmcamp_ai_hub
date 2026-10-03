# Cache techniques for AI agents · measured experiments

Six standalone notebooks, each built around an agent use case that AI developers will recognise. Every notebook explains the technique first, draws its request flow and its place in the agent's memory as Mermaid diagrams (embedded as images, with the Mermaid source in each diagram cell), then builds the cache in short, explained cells and measures it against real providers. The notebooks are saved with the outputs of a full live run.

The interactive [Cachecraft appbook](appbook/README.md) compares every technique side by side and runs live Tokenomics workloads. Start it on **http://localhost:8033** with the appbook instructions.

| Notebook | Use case | What it builds and measures |
|---|---|---|
| [01 Exact-match cache on Oracle True Cache](01_normal_cache.ipynb) | GitHub issue-triage agent with at-least-once webhooks | Response cache table written on the primary and read through True Cache with a primary fallback; replication lag, redeliveries, TTL, invalidation without cache code |
| [02 Embedding cache](02_embedding_cache.ipynb) | Coding agent re-indexing its long-term memory | Oracle-backed vector cache keyed by model, revision, settings and content hash; cold vs warm re-index, edits, configuration changes, reranked retrieval |
| [03 Semantic cache from scratch](03_semantic_cache_from_scratch.ipynb) | Developer-support agent answering duplicate questions | Raw Oracle VECTOR table and HNSW index, threshold calibrated on real duplicate pairs, reranker verification, scope, expiry and known failure modes |
| [04 Prompt cache](04_prompt_cache.ipynb) | Coding agent with stable instructions, tools and project memory | Anthropic cache writes and reads from reported usage, prefix invalidation, 5-minute vs 1-hour TTL, break-even |
| [05 Tool cache](05_tool_cache.ipynb) | Research agent repeating web searches | Oracle JSON tool-result cache with canonical arguments, preserved collection time, expiry, and side-effecting tools that are never cached |
| [06 Layered cache stack](06_unified_cache_stack.ipynb) | Developer-support agent over a Django knowledge base | Exact (True Cache), embedding, semantic (OracleSemanticCache), prompt and tool layers added one at a time on the same workload |

Embeddings and reranking use open-source Hugging Face models that run locally on the CPU: [`sentence-transformers/all-MiniLM-L6-v2`](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2) (384 dimensions) and [`cross-encoder/ms-marco-MiniLM-L-6-v2`](https://huggingface.co/cross-encoder/ms-marco-MiniLM-L-6-v2), both pinned to a revision. No embedding API key is needed. Data comes from public Hugging Face datasets pinned to a revision ([SWE-bench Lite](https://huggingface.co/datasets/SWE-bench/SWE-bench_Lite) and [StackExchange duplicates](https://huggingface.co/datasets/sentence-transformers/stackexchange-duplicates)), read with pandas.

## Run the notebooks

```bash
cd cache_techniques   # from the repository root
python3.12 -m venv .venv            # use a native arm64 Python on Apple silicon
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/jupyter lab
```

Each notebook starts with a `%pip install -q -r requirements.txt` cell for the active kernel; restart the kernel after the first install. Keys are requested with `getpass`: Anthropic for every notebook, Tavily for 05 and 06. The first run downloads the two local models (about 90 MB each) and the datasets.

Oracle requirements:

- **Vector schema** (02, 03, 05, 06): a dedicated schema on Oracle AI Database 23ai or later with `CREATE TABLE`, tablespace quota and a vector memory pool for HNSW. Set `ORACLE_USER`, `ORACLE_PASSWORD` and `ORACLE_DSN`, or enter them when prompted. `appbook/provision_local.py` creates one in a local container. Never use SYS or SYSTEM.
- **True Cache pair** (01, 06): see below. Set `TRUE_CACHE_USER`, `TRUE_CACHE_PASSWORD`, `PRIMARY_DSN` and `TRUE_CACHE_DSN`, or enter them when prompted.

## Oracle True Cache setup (Docker)

True Cache has no separate image: the Oracle Database Free image runs twice, once as the primary and once in True Cache mode. Port 1521 is often taken by another local database, so the primary is published on **1525** and True Cache on **1526**. On Apple silicon, pull the native image first: `docker pull --platform linux/arm64 container-registry.oracle.com/database/free:latest`. True Cache and the primary together need about 4 GB of Docker memory.

1. Network and primary database; wait for `DATABASE IS READY TO USE!`:

   ```bash
   docker network create --subnet 172.28.0.0/16 tc_net
   docker run -d --name pri-db-free --hostname pri-db-free --net tc_net --ip 172.28.0.10 \
     -p 1525:1521 -e ORACLE_PWD=<admin-password> container-registry.oracle.com/database/free:latest
   docker logs -f pri-db-free
   ```

2. Archive logging on the primary (`select log_mode from v$database` must show `ARCHIVELOG`; recent images already have force logging on, so `ORA-12920` from that statement is harmless):

   ```bash
   docker exec -i pri-db-free sqlplus / as sysdba <<'EOF'
   shutdown immediate;
   startup mount;
   alter database archivelog;
   alter database open;
   alter database force logging;
   alter pluggable database all open;
   select log_mode from v$database;
   EOF
   ```

3. The True Cache container. Current images also require `TRUEDB_UNIQUE_NAME` (the container exits with "TRUEDB_UNIQUE_NAME parameter value is NOT passed" without it) and use `ORACLE_HOSTNAME` for the primary's callback:

   ```bash
   tmp=$(mktemp -d)
   docker exec pri-db-free bash -c 'cat $ORACLE_HOME/dbs/orapwFREE' > "$tmp/orapwFREE"
   docker create --name tru-cc-free --hostname tru-cc-free --net tc_net --ip 172.28.0.11 -p 1526:1521 \
     -e ORACLE_PWD=<admin-password> -e TRUE_CACHE=true -e TRUEDB_UNIQUE_NAME=FREE_TC \
     -e ORACLE_HOSTNAME=tru-cc-free -e PRIMARY_DB_PWD_FILE=/var/tmp/orapwFREE \
     -e PRIMARY_DB_CONN_STR=172.28.0.10:1521/FREE container-registry.oracle.com/database/free:latest
   docker cp "$tmp/orapwFREE" tru-cc-free:/var/tmp/orapwFREE && rm -r "$tmp"
   docker start tru-cc-free && docker logs -f tru-cc-free
   ```

4. Register the application service on True Cache (its database service is `FREE_TC`, the unique name above):

   ```bash
   docker exec -it pri-db-free bash -c '$ORACLE_HOME/bin/dbca -configureDatabase \
     -configureTrueCacheInstanceService -sourceDB FREE \
     -trueCacheConnectString 172.28.0.11:1521/FREE_TC \
     -trueCacheServiceName sales_pdb_tc -serviceName FREEPDB1 \
     -pdbName FREEPDB1 -sysPassword <admin-password> -silent'
   ```

5. Check it: `select database_role, open_mode from v$database` on `tru-cc-free` shows `TRUE CACHE` and `READ ONLY WITH APPLY`, and `v$true_cache` shows `HEALTHY`. Then create the application user and its private connection file:

   ```bash
   cd appbook && .venv/bin/python provision_true_cache.py --container pri-db-free
   ```

   Writes go to `127.0.0.1:1525/FREEPDB1`; reads go to `127.0.0.1:1526/sales_pdb_tc`. A row committed on the primary was readable through True Cache about 0.04–0.13 s later in our runs, and a write through True Cache fails with `ORA-16000`.

## Re-run and verify

Edit the notebooks directly. Each diagram is an embedded PNG with its Mermaid source in a collapsed block in the same cell; if you change a diagram, render the new source (for example with `npx @mermaid-js/mermaid-cli`) and replace the attachment. To re-run notebooks end to end and save their outputs:

```bash
.venv/bin/python tests/run_notebooks.py --env-file /path/to/private.env        # all six
.venv/bin/python tests/run_notebooks.py --env-file /path/to/private.env 01 03  # by prefix
```

The runner executes every cell, including the install cell, against the real providers and saves the outputs into each notebook. Outputs are checked for key and password values before anything is written; a failed run leaves the notebook unchanged.

No model response, API usage count or cache hit is fabricated. Costs are list-price estimates (Claude Opus 5.5 prices checked on 2026-10-03; Tavily $0.008 per credit) from reported usage, not invoices. A handful of requests is an illustration, not a production benchmark; repeat the measurements on your own workload.

`cache_course.py` holds the reviewed helpers used by the appbook.

References: [Anthropic prompt caching](https://platform.claude.com/docs/en/build-with-claude/prompt-caching), [Oracle True Cache](https://docs.oracle.com/en/database/oracle/oracle-database/23/odbtc/), [Oracle AI Vector Search](https://docs.oracle.com/en/database/oracle/oracle-database/23/vecse/), [Tavily credits](https://docs.tavily.com/documentation/api-credits), [langchain-oracledb](https://github.com/oracle/langchain-oracle/tree/main/libs/oracledb).
