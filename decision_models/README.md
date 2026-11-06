# Decision Models in Agent Memory

Seven techniques from an agent's memory, each built the way it is usually built, broken on the
cases where it fails, swapped for a decision model, and measured against the original on the same
labelled data. Ten notebooks, one shared `harness/` package and an appbook.

Every swap notebook has the same four parts:

1. **Today** · the technique as it is usually built (a similarity score, a threshold, a rule or an LLM prompt).
2. **Where it breaks** · the cases where today's approach gives the wrong answer, run live.
3. **With a decision model** · the question asked directly, with a probability for each allowed answer.
4. **Which is better?** · both on the same labelled set, ending with a scorecard: the numbers and a
   plain verdict (better, level or worse, from a paired bootstrap), then the takeaways.

The agent is a [MemoRizz](https://github.com/RichmondAlake/memorizz) `MemAgent`. The decision model
in notebooks 01 to 07 is [`LiquidAI/d1-2B`](https://huggingface.co/LiquidAI/d1-2B), run locally;
notebook 09 asks the same questions of TypeSafe's Jev and OpenAI's Decisions API.

## Notebooks

| Notebook | The swap: today → with a decision model | Decision points |
|---|---|---|
| `00_memagent_baseline` | the agent, the reference architecture and the twenty decisions | all 20, listed |
| `01_semantic_chunking` | a similarity drop at a percentile → "does a new topic start here?" | 1 |
| `02_reranking` | cosine order or a cross-encoder → "does this chunk answer the query?" | 16 |
| `03_semantic_cache` | cosine above 0.9 → "can this cached answer serve this query?" | the cache in front of recall |
| `04_memory_routing` | the nearest store description → "which memory types does this need?" | 13, 14 |
| `05_consolidation` | cosine above 0.95 → same, refines, contradicts, complements or unrelated | 6, 7, 8, 10 |
| `06_memory_extraction` | an extraction prompt on every turn → "anything durable, and what type?" first | 2, 3 |
| `07_tool_selection` | top 3 tools by similarity → "which tool does this need, if any?" | 19 |
| `08_scoreboard` | the seven scorecards side by side, and where a decision model pays | all seven |
| `09_decision_model_providers` | d1, Jev and OpenAI Decisions on every swap's question | all seven |

Each notebook has a ⭐ live-path table at the top, and every cell has saved output. The pages of
[`docs/the-decision-on-decision-models.pdf`](docs/the-decision-on-decision-models.pdf) sit where they
belong: the reference architecture, the four stages and what a decision model is in notebook 00,
each technique and its swap at the top of its notebook, the pattern and where it pays in 08, and how
decision models are built in 09.

## Setup

Python 3.11. About 4 GB of memory for the model in bfloat16 on CUDA or Apple `mps`; it also runs in
float32 on CPU, with more memory and slower calls.

```bash
cd decision_models
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m ipykernel install --user --name decision-models
cp .env.example .env   # add OPENAI_API_KEY, and TYPESAFE_API_KEY for notebook 09
```


Open the notebooks in VS Code with the `decision-models` kernel. Each swap notebook stands on its
own; notebook 03 reads the cost of a full agent turn from notebook 00's results, and notebook 08
reads the scorecards notebooks 01 to 07 wrote to `results/`.

```bash
.venv/bin/python -m pytest tests -q        # fast checks, no model calls
.venv/bin/python tests/run_notebooks.py    # every notebook, outputs saved in place
.venv/bin/python tests/run_notebooks.py 03 # one notebook
```

### The appbook

`appbook/` is the interactive companion, in the same four-part shape: the reference architecture,
then one page per swap with the verdict first, today and the decision model side by side, the
notebook's "where it breaks" examples asked live of d1, Jev and OpenAI Decisions, the notebook's
scorecard, a live run over its labelled set, and the takeaways. It runs in this folder's `.venv`
and reads the same `.env`.

```bash
cd appbook && ./run.sh      # http://127.0.0.1:8740
```

See [`appbook/README.md`](appbook/README.md).

### Backends

`harness/d1.py` sends every question through `decide` and `decide_batch`, so the backend is one
environment variable, or `with d1.using(...)` for one block. No notebook changes.

| `D1_BACKEND` | Model | Endpoint | Key |
|---|---|---|---|
| `local` (default) | `LiquidAI/d1-2B` | this machine | none |
| `hosted` | Liquid `d1.1` | `https://api.liquid.ai/decisions/v1/systemone` | `LIQUID_API_KEY` |
| `jev` | TypeSafe `jev-1.14.0` (`JEV_MODEL` to change) | `https://api.typesafe.ai/v1/systemone` | `TYPESAFE_API_KEY` |
| `openai` | `gpt-6-luna` | `https://api.openai.com/v1/decisions` | `OPENAI_API_KEY` |

Liquid and Jev take the same request. OpenAI's Decisions API takes a different one: `input` for
`state`, a list of questions, `predicate` for `noul`, and options as objects. A predicate has no
criteria field, so a noul's criteria go into its instructions. Answers are translated back, so every
backend returns the same shape. Liquid's hosted backend has not been run here.

## Layout

```
docs/        the-decision-on-decision-models.pdf (the reference architecture, the four stages, decision
             models and the seven swaps; its pages are rendered into notebooks/img/reference/)
data/        demo_text.md  demo_text.json  eval_questions.json  labels_*.json
harness/     questions.py (every swap's question)  d1.py  measure.py (scorecard)  spans.py  charts.py
             demo_tools.py  decision_points.py
notebooks/   00 .. 09, and img/ for the diagrams and the PDF's pages
results/     <notebook>.jsonl, one per notebook: the scorecards notebook 08 and the appbook read
tests/       test_harness.py  run_notebooks.py
tools/       diagrams/render.py renders the Mermaid sources to PNG
appbook/     the interactive companion (FastAPI + vanilla JS) on port 8740
memory_store/   the FileSystemProvider root (gitignored)
```

## About the data

Everything is synthetic. `data/demo_text.md` is a support call of about 1,500 words across eight
topics, and the card number in it is the standard test number `4111 1111 1111 1111`. Eight topics
make seven real cuts, because the first topic starts at offset zero.

The label files were written by hand before any model saw them and are not edited after seeing
results: `labels_cache.json` (48 lookups against 16 cached answers), `labels_memory_routing.json`
(58 turns, 12 needing two stores), `labels_dedup.json` (50 memory pairs, ten per relation),
`labels_extraction.json` (60 turns, 36 worth remembering) and `labels_tools.json` (75 turns over
eleven tools). The same author wrote the labels and the tool descriptions, which flatters every
method a little; the examples are small and easy next to a real system.
`eval_questions.json` was generated by `gpt-4o-mini` (`data/build_eval_questions.py`), filtered to
exact substrings, de-duplicated by embedding similarity, then reviewed.

## Licences

- **`LiquidAI/d1-2B`** is under the [LFM Open License v1.0](https://huggingface.co/LiquidAI/d1-2B/blob/main/LICENSE).
  Commercial use is licensed only for legal entities with under $10M annual revenue. The notebooks
  download the weights rather than redistribute them.
- **MemoRizz** is under the PolyForm Noncommercial License 1.0.0.

Check both before taking these notebooks into work.

## What the saved run found

One run of every notebook on a 16 GB Apple M5 on 2026-11-06, with d1 on the laptop's GPU. One
synthetic transcript and label sets of 40 to 75 items: read this as a way to run the comparison on
your own data, not as a ranking. Verdicts are paired bootstraps, 95% interval of the gain.

| Swap | Today | Main measure | Today | d1 | Verdict | Also measured |
|---|---|---|---|---|---|---|
| 1 · Semantic chunking | semantic p95 | retrieval hit rate | 0.95 | 0.93 | level | twice the utilisation (0.04 → 0.07, better); 5 of 7 topic changes found against 3 |
| 2 · Reranking | cross-encoder | nDCG@5 | 0.71 | 0.89 | **better** | recall@5 0.82 → 0.97; but 963 ms against 14 ms per 20 candidates |
| 3 · Semantic cache | cosine ≥ 0.9 | right decisions | 0.58 | 0.98 | **better** | paraphrases served 2 → 20 of 20; wrong answers 2 → 1; pays off above a 0.6% hit rate |
| 4 · Memory routing | nearest store | right route | 0.45 | 0.67 | **better** | two-store turns 0 → 8 of 12; an LLM prompt scored 0.47 to 0.55 across runs; one Choice ties on exact routes but serves no two-store turn |
| 5 · Consolidation | cosine > 0.95 | right action | 0.20 | 0.88 | **better** | contradictions caught 0 → 10 of 10 |
| 6 · Memory extraction | prompt on every turn | turns handled right | 0.97 | 1.00 | level | 23 of 60 prompt calls skipped, about a fifth cheaper; the prompt names the type better (0.97 against 0.86) |
| 7 · Tool selection | top 3 by similarity | right tool first | 0.71 | 0.96 | **better** | wrong tool calls 4 → 0; prompt tokens 247 → 100 per turn |

### Notebook 09: three decision models

Every swap's question, word for word, on the same labels, at the same 0.5 line. Cost is for all
1,340 requests at each provider's input price, with d1 at Liquid's hosted rate.

| Swap | Measure | d1 | Jev | OpenAI Decisions |
|---|---|---|---|---|
| 1 · Chunking | boundary F1 | **0.48** | 0.32 | 0.31 |
| 2 · Reranking | nDCG@5 | 0.89 | 0.90 | **0.94** |
| 3 · Semantic cache | right decisions | 0.98 | 0.98 | **1.00** |
| 4 · Memory routing | right route | **0.67** | 0.38 | 0.43 |
| 5 · Consolidation | right action | 0.88 | **0.90** | **0.90** |
| 6 · Extraction | gate right | 0.98 | **1.00** | **1.00** |
| 7 · Tool selection | right tool first | 0.96 | 0.96 | **0.97** |
| Median ms per request | | **151** | 190 | 238 |
| USD for all seven sets | | **0.004** | 0.022 | 0.036 |

On five swaps the three land within a few items of each other. Chunking and routing separate them:
the hosted models' probabilities sit on their own scales (Jev and OpenAI cut about 30 extra times at
0.5; in routing Jev says yes to too many stores and OpenAI to too few), and the routing criteria were
written with d1. Set thresholds per model, on your own labels.

### Notes on the thresholds and examples

- **Dedup threshold:** MemoRizz 0.17.16 treats near-identical summaries as duplicates from cosine
  0.97 (`learning/consolidation.py`); 0.95 is used here as the common setting. With
  `text-embedding-3-small`, no reworded duplicate reached 0.95, so the cut-off inserted everything.
- **Semantic cache threshold:** MemoRizz's `SemanticCache` defaults to 0.78; notebook 03 uses 0.9 and
  shows both.
- **Chunking:** the percentile cut merged the two memory sections, as expected. It did not split the
  code sample from its explanation, because the sentence splitter keeps a code block glued to the
  sentence after it.

## Notes for running it

- **`model.compile()` is not used.** On `mps` each new batch shape took about 20 seconds to compile,
  and a single call only went from 60 ms to 56 ms.
- **`harness/d1.py` lowers the token budget** to 6,000 padded tokens off CUDA and sets an MPS memory
  ceiling. At the default of 65,536, long states thrashed a 16 GB machine.
- **Choice options:** the local model accepted 1,000 options in a quick test, with confidence falling
  as options grew. The 254 limit in `memorizz.benchmarks.jev_reranking` belongs to MemoRizz. Hosted
  limits are not documented.
- **More than 16 questions in a request** work: extra questions run in further passes over the state.
