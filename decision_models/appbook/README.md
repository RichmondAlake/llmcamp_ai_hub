# Decision Models in Agent Memory — App

The interactive companion to the ten notebooks in [`../notebooks/`](../notebooks/). The notebooks
build and measure each comparison; this app shows the same seven swaps live. Every swap page has
the notebooks' shape:

1. **The verdict first:** the notebook's scorecard as one sentence, today's number against the
   decision model's, and better, level or worse.
2. **Today and with a decision model,** side by side, plus how the notebook judged them.
3. **Where it breaks, live:** the notebook's own examples (or your input) run through today's method
   and every chosen decision model, each answer marked right or wrong against the labels.
4. **Which is better?** The notebook's full scorecard, a chart where one helps, and a live run of the
   notebook's labelled set through one decision model.
5. **The takeaways.**

Three decision models answer the same request:

| Model | Maker | Runs | Called through |
|---|---|---|---|
| `LiquidAI/d1-2B` | Liquid AI | this machine, open weights | `model.system_one(state, questions)` |
| `jev-1.14.0` | TypeSafe | hosted | `POST api.typesafe.ai/v1/systemone` |
| `gpt-6-luna` | OpenAI | hosted | `POST api.openai.com/v1/decisions` |

| Page | Notebook | Today → with a decision model |
|---|---|---|
| Reference architecture | 00 | the twenty decision points by stage, the seven swaps and their verdicts, the stores each point touches |
| 1 · Semantic chunking | 01 | SemanticChunker at the 95th percentile → "does a new topic start here?" at every gap |
| 2 · Reranking | 02 | cosine order and a cross-encoder → "does this chunk answer the query?", sorted by P |
| 3 · Semantic cache | 03 | cosine ≥ 0.9 → "can this cached answer serve this query?"; the threshold-trap chart |
| 4 · Memory routing | 04 | nearest store description, or an LLM prompt → one yes or no per memory type; why not one Choice |
| 5 · Consolidation and dedup | 05 | cosine > 0.95 → same, refines, contradicts, complements or unrelated; similarity by relation |
| 6 · Memory extraction | 06 | extraction prompt on every turn → a gate and a type first |
| 7 · Tool selection | 07 | top 3 by similarity → a Choice over the top 5, plus none |
| Scoreboard | 08 | the seven scorecards, the cost table, the pattern and where it pays |
| Three decision models | 09 | notebook 09's comparison, and a playground: one state, your questions, every model |
| Tokenomics | — | every request this session sent: latency, input tokens and cost per model |

Every question is `harness/questions.py`, the same words the notebooks ask (tests check that they
match).

The **Model context** rail on the right shows the last decision exactly as each model received it:
the request body (OpenAI's after translation), the answers in d1's shape, and OpenAI's raw reply.
The **Data Explorer** at the bottom reads the label files, every notebook's `results/*.jsonl`, this
session's decisions and the MemoRizz store, read-only.

## Run

```bash
cd decision_models/appbook
cp .env.example .env        # optional: the app also reads ../.env (OPENAI_API_KEY, TYPESAFE_API_KEY)
./run.sh                    # → http://127.0.0.1:8740
```

`run.sh` uses `$PYTHON` if set, otherwise the notebooks' `../.venv/bin/python`, otherwise
`python3`. The notebooks' requirements must already be installed there (MemoRizz, Transformers,
torch, sentence-transformers, LangChain); the app adds FastAPI, uvicorn and sse-starlette when an
import check fails. `HOST` and `PORT` override the address.

## Requirements and failure behaviour

- **d1** loads on the first local decision, or from **Load** on the status card: about 7 GB and
  10 to 20 seconds. `DM_PRELOAD=1` loads it at start. If it fails to load, the hosted models still
  answer and the status card shows the error.
- **Jev** needs `TYPESAFE_API_KEY`; **OpenAI Decisions**, the typical LLM paths and MemoRizz's
  embeddings need `OPENAI_API_KEY`. A model without its key is greyed out in every chooser.
- A hosted call that times out or is rate-limited is retried three times, then shown as an error on
  its card; the other models' answers still appear.
- Keys are read from the environment and never sent to the browser.
- **The lab session** scopes everything: its MemoRizz store is
  `../memory_store/appbook-<session>` (the knowledge base for the reranking labelled set, the toolbox
  for tool selection) and its decision log is `data/sessions/<session>.jsonl`. **Reset** on the status card
  starts a new session. Both are kept by default; `DM_CLEANUP=1` deletes them on reset and on
  shutdown.
- The verdicts, scorecards, Scoreboard and Three decision models pages read saved results from
  `results/`; they need notebooks 01 to 09 to have run. Nothing on those parts calls a model.

Hosted answers can differ from run to run (Jev routed 22 and 21 of 58 turns in two runs of the same
set). d1 is deterministic. Today's methods use OpenAI embeddings, which also vary slightly: the
semantic chunker can cut the example page once or not at all.

On a 16 GB machine that is already short of memory, keep d1 unloaded (the default) and ask the
hosted models; a d1 that has been paged out to swap can take minutes to answer its next request.
`MODELS=jev,openai tests/check_live.py` checks the hosted models alone.

## Tests

Run them one at a time.

```bash
../.venv/bin/python -m pytest tests/test_contracts.py -q   # offline: routes, schemas, allowlist, policies, no keys in replies
../.venv/bin/python tests/check_live.py                    # real models against a running app (a few cents)
../.venv/bin/python tests/check_browser.py                 # every page at desktop and phone width; screenshots in tests/artifacts/
```

## Architecture

```
appbook/
  backend/
    main.py            FastAPI app, static frontend, /img from ../notebooks/img
    config.py          paths, the three models, settings; puts ../ on sys.path for `harness`
    schemas.py         request bodies, capped
    core/
      models.py        one call to any backend; batches; request as sent; cost
      swaps/           one module per swap notebook: what today does, the decision model's question,
                       the notebook's examples, try one input, the labelled set and its scorer
        common.py      embeddings, the chat model, the method record every page draws
        chunking.py  reranking.py  cache.py  routing.py  consolidation.py  extraction.py  tools.py
      evidence.py      the notebooks' scorecards and notebook 09's comparison, from results/
      architecture.py  the twenty points, placed, with their swap's verdict
      session.py       the lab session, its store and its log
      explorer.py      the read-only Data Explorer
      sse.py           progress for label-set runs
    routers/           meta, reference, decisions (the swaps and the playground), tokenomics, data_explorer
  frontend/            index.html, styles.css (shared), decide.css, app.js, charts.js,
                       architecture.js, pages.js (the swap page), results.js — no build step
  tests/               test_contracts.py, check_live.py, check_browser.py
```
