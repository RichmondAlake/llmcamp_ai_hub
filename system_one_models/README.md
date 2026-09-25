# System One Models: decisions inside an agent-memory pipeline

Six educational experiments, built from scratch with **Python, SQL and HTTP**.
Every notebook uses a Docker-hosted **Oracle AI Database**. Voyage supplies the
embeddings, **GPT-6 Luna** supplies generation and the LLM reranker, and TypeSafe Jev supplies typed decisions.
The final reader lesson compares **Claude Opus 5.5, GPT-6 Sol and GPT-6 Luna**.

Start with [the setup notebook](00_oracle_setup.ipynb), then work through the lessons.
Code cells are at most **25 lines**. Provider calls, policies, labels, SQL, and metric
formulas are visible in the notebooks; they do not import a hidden experiment engine
or use an agent/RAG framework. The appbook reuses the experiment functions and uses
Oracle's **langchain-oracledb** integration for vector-table setup and ingestion.

⭐ marks the main learning path: understand the failure, inspect the data, build the
decision, run the comparison and interpret the evidence. Run all cells in order in a
fresh kernel. The authored fixtures live in [datasets](datasets/) as readable JSON;
keep that folder beside the notebooks. Dataset tables and saved outputs remain in
each lesson. The appbook's **Download lesson + data** button packages the required files.

| Lesson | What you build | What the test actually measures |
|---|---|---|
| [00 — Oracle setup](00_oracle_setup.ipynb) | Docker, restricted account, native VECTOR query | Database connectivity and vector arithmetic |
| [01 — Reranking](01_reranking.ipynb) | Original order, Voyage, OpenAI, MiniLM, Jev Noul/Score/Choice | Precision, recall, MRR, graded nDCG, candidate ceiling, ranking latency/cost, fixed-reader outcomes |
| [02 — Summary quality](02_summary_quality_gate.ipynb) | No gate, Jev verifier, OpenAI verifier | Bad-summary admission, good-summary rejection, coverage, latency and cost; development-only threshold fitting |
| [03 — Memory routing](03_memory_use_routing.ipynb) | Always, never, Jev before search, Jev after retrieval | Whether to search/use memory, actual path cost, and resulting answers |
| [04 — Tools and skills](04_toolbox_skillbox_selection.ipynb) | Embedding top-1, embedding + Jev, eligible catalog + Jev | Correct selection, abstention, false activation and candidate recall; no tool execution |
| [05 — Semantic chunking](05_semantic_chunking.ipynb) | Fixed, sentence-aware, embedding-change and Jev boundaries | Source-span precision/recall/IoU under the same 70-word budget, ingestion economics and OpenAI answers |
| [06 — Memory readers](06_memory_reader_comparison.ipynb) | Opus 5.5, GPT-6 Sol, GPT-6 Luna | Reading identical memory evidence, usage, latency and lexical answer checks; human factual review remains separate |

## How Jev differs—and where to put it

A generative LLM produces an answer or a summary. Jev evaluates a question against
provided state and returns a typed decision. **Choice** distributes probability over
options; **Score** distributes probability over ordered rubric levels; **Noul** gives
a value from 0 to 1 for a statement. A concentrated distribution is not proof that the
decision is correct. Validate it against labels appropriate to your application.

The useful design is often: an LLM generates, Jev judges an atomic property, and Python
applies a policy. An LLM with structured output can also make typed decisions; it is an
important baseline, not something to dismiss because its output is structured JSON.
The advantage must be demonstrated in quality, cost and latency on the same workload.

Memory-use routing contains two different decisions. **Before retrieval**, a router
decides whether searching the available memory bank seems worthwhile, without seeing
what it will find. **After retrieval**, it decides whether the actual evidence should
enter the answer context; search has already been paid for. Explicit user memory-off
preferences are enforced by code before either decision. Lesson 03 executes all four
paths, rather than estimating savings from a classification score alone.

Jev does not replace the vector database or an embedding model. It can reorder retrieved
candidates, but cannot recover evidence outside its pool. It can choose an applicable
tool or skill, but the application still enforces eligibility and execution permission.
It can choose chunk boundaries, but source offsets and size limits remain code concerns.

Writing new memories into Oracle is **external memory adaptation**. None of these
lessons updates model weights or proves continual learning in the training sense.
For that claim, add sequential tasks, a frozen baseline, forgetting/retention tests,
and adaptation measurements over time. Keep original source material when exploring
summary gates; a lossy summary should not be the only evidence you retain.

## Install and run locally

Use Python 3.12 and start Docker Desktop. In this folder:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
```

The notebooks prompt only for the providers they use, using **getpass**. For the
appbook, configure the required keys in the private server-side `.env`:

| Experiments | Required provider keys |
|---|---|
| Reranking, summary quality, memory routing, semantic chunking | `TYPESAFE_API_KEY`, `VOYAGE_API_KEY`, `OPENAI_API_KEY` |
| Tool/skill selection | `TYPESAFE_API_KEY`, `VOYAGE_API_KEY` |
| Opus/Sol/Luna memory readers | `VOYAGE_API_KEY`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY` |

Set a strong `ORACLE_ADMIN_PASSWORD`, a separate
`ORACLE_PASSWORD`, `ORACLE_USER=s1lab`, and `ORACLE_DSN=127.0.0.1:1535/FREEPDB1` for
a new container. No key belongs in a notebook output, Git commit, or browser form.

```bash
docker compose up -d
docker compose ps
# Wait until healthy, then create the restricted account once:
python bootstrap_oracle.py
```

Open the notebooks in VS Code or your local Jupyter installation, using this environment
as the kernel. The setup notebook explains each step. On a remote kernel, `localhost`
does not refer to your laptop. Configure a reachable Oracle endpoint instead.

The compose default uses Oracle's `latest-lite` image with amd64 emulation. The setup
lesson records the actual database version; record image digests when freezing a study.
Allow sufficient Docker disk and memory before creating a database. Existing Docker
Oracle instances can be reused with a separate account and `ORACLE_DSN`; no destructive
reset is required. Fresh-install compose uses **1535** to avoid conflicting with an
existing listener; set `ORACLE_DSN` to the port exposed by your chosen container.

The local reranker downloads `cross-encoder/ms-marco-MiniLM-L-6-v2` once. Loading time
is separate from warm CPU inference. `LOCAL_HOURLY_USD` optionally prices inference
compute; external API charge remains zero. Record hardware and model revision when
comparing it with hosted services. No GPU acceleration is assumed.

## Run the educational appbook

```bash
python appbook/server.py --port 8878
```

Open **http://127.0.0.1:8878**. Each chapter has **Understand**, **Build it**, and
**Experiment** views. Read the experimental contract, inspect every notebook cell,
run real calls, and explore the Oracle results. Charts show quality, latency/cost and
per-question changes. Expand cases for labels, decisions, evidence and answers; export
JSON for analysis. The appbook uses the Python standard-library HTTP server and native
SVG charts. It has no hosted telemetry, chart CDN, or browser-side API credentials.

Understand includes concrete examples and technical architectures with component icons
and labeled arrows. Experiment updates after each saved result, with an in-flight call
indicator and partial-sample labels. Click a metric column to sort in either direction;
hover or focus its information button for the definition and denominator. Metrics and
timing scopes adapt to the experiment. The Voyage reranker is **rerank-2.5**; embeddings
use **voyage-4**. Protocol v3 uses **gpt-6-luna** with `reasoning.effort="none"` for
short generation, verification and reranking tasks. The separate Opus/Sol/Luna reader
comparison retains **medium** effort and a 4,096-token cap. Opus 5.5 keeps adaptive thinking enabled; the same effort label does not imply equal compute across providers. Reranking readers receive
only source IDs and text, so method-specific scores cannot influence their answers.
Historical runs retain their original model, prices and protocol labels.

`langchain-oracledb==1.5.0` is installed through the requirements file. The appbook's
[Oracle storage adapter](appbook/oracle_storage.py) delegates vector-table creation
and batch insertion to `OracleVS`, using the same measured Voyage calls. Exact SQL
retrieval retains the experiment's deterministic distance/source-ID order. New appbook
sources live in `S1_VECTORS`; notebook sources remain in `S1_DOCUMENTS`. Both are visible
in the database explorer, including run filters, full records and observed appbook
reads/writes. The notebooks keep their shorter explicit SQL implementation.

One appbook worker runs at a time. Notebook runs also use live services, so avoid launching
many independent kernels unintentionally. The appbook and example `.env` stop between
requests at 1,000 recorded calls or an estimated $5 per run. A notebook with no
`S1_MAX_CALLS` environment setting retains its 300-call fallback. These are stop
thresholds, not hard invoice guarantees.
Failures are retained; no canned response replaces a failed provider request.

Reranking and memory readers offer **1–40 distinct labeled questions**, with six selected
by default. The input shows the available range; larger values require adding labeled
questions to `datasets/questions.json` and restarting the appbook. A 40-question reranking
run executes seven methods per question: **280 result rows and 561 recorded calls**
(521 hosted calls and 40 local reranker calls). This includes one shared ingestion call,
one embedding call per query, five hosted rerankers, one CPU reranker and seven reader
calls per query. A lower configured request cap is checked before starting the run.
The other lessons show the capacity of their own datasets rather than repeating examples.

## Replicate the reranking test in Memorizz

After successfully executing lesson 01:

```bash
python export_memorizz.py
python launch_memorizz.py --repo /path/to/memorizz --port 8766
```

The launcher requires the **updated local Memorizz checkout** and its UI/OpenAI/Anthropic
dependencies in the executing environment. It does not assume these new comparison
features are already published in a released PyPI version. With a fresh environment,
install that checkout using `python -m pip install -e '/path/to/memorizz[ui,anthropic]'`.

Open **http://127.0.0.1:8766/evalground/compare** and open **Start from a sample configuration** in the Dataset step, then choose **7 reranking methods**. The preset fills model lists, Jev recipes, six questions, twenty candidates,
and top-three evidence. **3 answer models** configures the three readers
with five evidence items, medium effort, and a 4,096-token output budget.

The export comes from Oracle's completed run record and contains source text, IDs,
candidate order, labels, provenance and a checksum. Memorizz makes **new live reranker
and reader calls** with its own adapters. It does not replay model responses or replace
Voyage retrieval with Ollama. Original embedding work is recorded as source provenance;
replay serving latency/cost includes reranking and reading, excluding that earlier work.
Prompt serialization differs between the from-scratch and Memorizz adapters, so this
replicates the experimental design and frozen inputs, not an identical network payload.

The launcher's filesystem provider stores only isolated UI session metadata. Experimental
evidence originates in Oracle. The export boundary deliberately freezes candidates so
you can attribute quality differences to the component being tested. This is a Memorizz
Evalground diagnostic, not a complete autonomous MemAgent or production memory service.

## Read the numbers correctly

- **Precision@k:** relevant returned IDs divided by requested k. Missing slots are not free wins.
- **Recall@k:** relevant returned IDs divided by all positive gold IDs, including first-stage misses.
- **MRR@k:** reciprocal rank of the first relevant result within k; zero if none appears.
- **nDCG@k:** graded gains `2**grade - 1`, logarithmic discount, full-gold ideal ordering.
- **Candidate recall:** the first-stage pool's ceiling. A reranker cannot exceed it.
- **Answer checks:** keyword diagnostics, not reliable factual-accuracy judgments. Inspect answers against sources before claiming a winner.
- **Latency:** actual client wall time. Distinguish model loading, ranking, reading, ingestion and network effects. Six observations do not establish production p95.
- **Cost:** dated list-price estimate from provider-reported tokens. Cached reads and cache writes are subsets of input and are priced separately. Reasoning is included in output, not billed twice.

Unknown prices and missing usage remain unknown. The lesson's costs do not infer account
credits or free tiers. Jev Choice probabilities are pool-relative, not globally calibrated
relevance thresholds. In the chunking lesson, ingestion totals repeat per query for
inspection—do not sum that repeated column. The call ledger is the spend source of truth.

These are authored synthetic teaching fixtures: 30 source memories and up to 40 memory
questions, 10 summary examples with a development/test split, 8 routing cases, 8 catalog
requests, and 6 chunk-retrieval questions over 3 documents. Start with the six-question
reranking run, then replace the fixtures with independent, representative conversations.
The extra questions cover the same small corpus; they are not 40 independent conversations.
Existing notebook outputs retain the original six-question executions and earlier dataset
previews. Re-running loads the current JSON fixtures; the default experiment still uses six.
Prompt/rubric selection is part of the method. Do not describe a tuned small teaching
set as a held-out production benchmark or a general model leaderboard.

There are concrete limits to the exercises. The catalog test has two no-tool cases:
an always-select embedding baseline cannot abstain, so improved exact-set accuracy
does not establish better positive-item ranking. The chunking corpus contains just
three short documents; methods can produce identical boundaries. The routing labels
express expected memory use, not proven improvements to an answer. Summary candidates
are authored examples, not a representative sample from a production extractor.
Lexical checks can reject a correct paraphrase or accept a wrong claim containing
the expected word. Human-reviewed answers and larger independent conversations are
needed before choosing a production model.

## Validation and reproducibility

```bash
python -m unittest discover -s tests -v      # Offline contracts and arithmetic
RUN_ORACLE_INTEGRATION=1 python -m unittest discover -s tests -v  # Also test local Oracle storage
python execute_notebooks.py                # Real calls, Oracle, and executed outputs
python audit_notebooks.py                  # Recompute billing and metrics from saved Oracle runs
```

The run-limit regression checks validate 40 distinct questions, all 280 case/method
combinations, request-cap checks and worker arguments using mocked provider execution.
The saved reranking notebook records a real six-question run; it does not claim to
contain a completed 40-question provider benchmark. Optional JavaScript arithmetic
checks run with `node tests/appbook_analysis.cjs`.

The live runner skips installation cells only; dependencies must already be installed.
It explicitly sets `S1_USE_ENV_KEYS=1` for non-interactive credential loading. Interactive
notebook runs default to hidden getpass prompts. The runner executes the actual notebook
cells and saves real outputs **in the original notebooks** and under `artifacts/executed/`.
`artifacts/execution_status.json` records outcomes. That generated directory is ignored
by Git; the root notebooks are the learner-facing record of an executed run. Provider
failures remain in Oracle and are not silently replayed as successful measurements.

Edit the notebooks directly to preserve their short cells, SQL indentation and saved
outputs. `lab_core.py` and `lab_experiments.py` implement the appbook's corresponding
runtime functions; notebooks contain their own complete code. When changing a provider
policy or metric, update both implementations and rerun the relevant validation.
There is no notebook-generation or conclusion-refresh script to run.

Teaching fixtures have one source: the adjacent `datasets/` JSON files, loaded by both
notebooks and the appbook. The appbook's explanations and diagram specifications live
in `appbook/lessons.json`. Notebook diagrams are embedded attachments, so they do not
depend on external image files. The appbook's lesson download packages the required data.

Each experiment follows nine parts, with checkpoints and an outline of learning steps
instead of one heading per helper. Dataset and result inspection use pandas DataFrames;
structured configuration and call logs use `pprint.pprint`. SQL is indented and split
into readable clauses. Diagrams are embedded PNG attachments and need no Mermaid extension.
Run the live validation runner again when changing an experiment. Keep local credentials,
runtime databases, generated validation reports and duplicate executed notebooks out of commits.

## Sources and teaching references

Read on September 25, 2026:

- [TypeSafe documentation index](https://docs.typesafe.ai/llms.txt), [HTTP API](https://docs.typesafe.ai/api), [Score](https://docs.typesafe.ai/primitives/score), [Noul](https://docs.typesafe.ai/primitives/noul).
- [TypeSafe skill](https://github.com/typesafe-ai/skills/blob/main/skills/typesafe-ai/SKILL.md), installed for Codex using the requested `npx skills add typesafe-ai/skills --skill typesafe-ai --agent codex --yes` method and applied in this project.
- [Voyage embeddings](https://docs.voyageai.com/reference/embeddings-api), [reranking API](https://docs.voyageai.com/reference/reranker-api), [pricing](https://docs.voyageai.com/docs/pricing).
- [OpenAI structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs), [prompt-cache billing](https://developers.openai.com/api/docs/guides/prompt-caching), [GPT-6 Sol](https://developers.openai.com/api/docs/models/gpt-6-sol), [GPT-6 Luna](https://developers.openai.com/api/docs/models/gpt-6-luna).
- [Claude models](https://platform.claude.com/docs/en/models/overview), [effort](https://platform.claude.com/docs/en/build-with-claude/effort).
- [Oracle vector bindings](https://python-oracledb.readthedocs.io/en/latest/user_guide/vector_data_type.html).
- [Oracle's langchain-oracledb integration](https://github.com/oracle/langchain-oracle/tree/main/libs/oracledb/langchain_oracledb), pinned to the tested pip release for appbook storage.
- Teaching style: [Agent memory from scratch](../agent_memory/agent_memory_from_scratch.ipynb) and [Oracle memory/context engineering notebook](https://github.com/oracle-devrel/oracle-ai-developer-hub/blob/main/notebooks/memory_context_engineering_agents.ipynb). This course implements its own plain Python/SQL/HTTP experiments rather than copying those notebooks' framework integrations.
