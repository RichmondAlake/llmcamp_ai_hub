# System One Appbook

An educational companion to the six from-scratch notebooks. Start Docker Oracle and
configure the parent folder's `.env`, then run from `system_one_models`:

```bash
python appbook/server.py --port 8878
```

Open **http://127.0.0.1:8878**.

**Understand** teaches the question, controls, before/after architecture and limitations.
**Build it** displays the actual notebook cells and offers the standalone notebook.
**Experiment** executes real provider calls in a worker process and reads the results
from Oracle. Select saved runs, inspect source evidence and labels, compare charts,
or export the call ledger. Provider credentials remain on the Python side.

Reranking and memory readers start with six questions and support up to 40. The input
shows the real dataset range, and reranking displays the planned result rows and calls.
Forty questions produce 280 case/method rows and 561 recorded calls, including 40 local
inference calls. The example request cap is 1,000; a smaller configured cap rejects a
run that cannot finish before making paid calls. The $5 estimated-spend stop remains.
The 40 questions share 30 authored memories, so this is still a small teaching dataset.
Other chapters use their own labeled examples and show their respective ranges.

The server uses `http.server`, the browser uses ordinary JavaScript and SVG, and the
experiment policies and provider calls remain explicit Python and HTTP.
The appbook is intended for local education; it binds to loopback.
`lessons.json` holds the chapter explanations and diagram specifications. The server
derives each maximum case count from its JSON dataset; defaults are separate settings.

## Oracle integration

Install `langchain-oracledb==1.5.0` with pip, or install the course requirements.
[oracle_storage.py](oracle_storage.py) uses Oracle's `OracleVS` for table creation,
FLOAT32 vector binding, JSON metadata and batch insertion into `S1_VECTORS`.
Its small embedding adapter calls the existing measured Voyage HTTP function, so
every real embedding call still appears in the cost/token ledger. The output dimension
is fixed and validated at 1,024; constructing the store makes no extra embedding call.

Retrieval retains exact cosine SQL and a source-ID tie-break. OracleVS's convenience
search uses an approximate-fetch query, which would change this benchmark's contract.
Collections include the run ID and are filtered in SQL before the top-k cutoff.
Source IDs and text returned to the experiment match the notebook's explicit SQL path.
No historical `S1_DOCUMENTS` or experiment records are migrated or overwritten.

The notebook storage code stays from scratch: using the integration there would add
adapter classes without shortening the complete teaching example. **Build it** displays
that standalone implementation; **Experiment** uses OracleVS ingestion. Saved run
details identify the storage backend, while provider policies and metrics are shared.

See the [course README](../README.md) for database installation, pricing scope,
datasets, test commands and the separate Memorizz Evalground replication.

## Oracle data explorer

The bottom panel stays available on every lesson and on Understand, Build it and
Experiment. Click its title to expand or collapse it. Drag its top edge to resize;
the focused separator also accepts ↑/↓, Home and End. Height and open state persist.

**Data** lists every table and view owned by the configured lab schema. Browse pages,
search text/JSON, sort supported columns, filter to the selected experiment, and open
a complete record, including its vector. Downloads contain the full record; the grid
deliberately uses short previews. Each data request uses an Oracle read-only
transaction, so its count and page share one consistent snapshot. No arbitrary SQL
or database mutation is exposed by this explorer.

**Activity** records actual appbook and worker SQL, with elapsed driver time, affected
or fetched rows, run/case/method and sanitized SQL. Table colors identify reads,
writes, commits and rollbacks. **Transactions** groups writes by a client correlation
ID and shows the observed outcome. These correlation IDs are not Oracle XIDs.
No bind values, credentials, document text or result payloads are stored in the log.

The journal is bounded local SQLite at `.data/appbook/database-activity.sqlite3`,
shared by the HTTP server and its subprocess workers. It is application tracing,
not database-wide auditing: independent notebook/database clients are not traced.
Their committed rows still appear when data refreshes. Catalog metadata polls are
omitted; the source filter can include explorer data reads. Closing or pausing the
panel stops automatic browser polling. It does not pause an experiment or prevent
its worker from recording events. Resume reads the retained recent history.

Transaction tracing delegates the caller's existing commit, rollback and close
operations; it introduces no extra Oracle writes or transaction boundaries. SQL
event durations exclude local journal I/O. Full experiment durations can include
the small application-instrumentation overhead.

Notebook downloads are ZIP bundles containing the notebook, its plain JSON fixtures,
Oracle setup notebook and setup files. Private `.env` files are never included.
