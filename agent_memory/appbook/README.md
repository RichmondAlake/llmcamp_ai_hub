# Agent Memory Appbook

A local, interactive companion to [the from-scratch notebook](../agent_memory_from_scratch.ipynb). Chat with a real OpenAI model, inspect its current input, change how it remembers, and follow facts back to their sources.

The charcoal, cream, gold, cyan and pink palette follows Richmond Alake's *Unpacking Agent Memory Patterns in GPT-6 Astra* presentation. Architecture diagrams are local SVGs, so they render without a Mermaid extension or external service.

## Run locally

Requires Python 3.10+ and an OpenAI API key with access to the selected model.

```bash
cd agent_memory/appbook
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
# Put your OPENAI_API_KEY in .env.
python server.py --port 8877
```

Open **http://127.0.0.1:8877**. On Windows, activate with `.venv\Scripts\activate` and copy the example using your shell's `copy` command.

The server binds to localhost. Keys remain on the server; they are never passed to the browser or written into memory. You can instead export environment variables or set `APPBOOK_ENV_FILE` to an existing environment file. `APPBOOK_DATA_DIR` changes the local storage directory.

The default model is `gpt-6-astra` with low reasoning. **Model & session settings** accepts another OpenAI model name. Changes apply to new sessions so an experiment keeps a consistent model. Use a model that supports Responses API function calls and structured output; access and supported reasoning settings vary by model.

## Explore the four labs

| Lab | Interaction | Evidence to inspect |
|---|---|---|
| Summarisation | Chat, select a summary rule, then **Summarise** | W1's original items, W2's summary seed, measured token change and an omitted detail |
| Offloading | Offload the whole window or completed tool exchanges | The synopsis, `offload_id`, `source_window_id`, linked `tool_call_ids`, and the executed retrieval |
| Comparison | One composer sends the same message to both agents; **Reduce both** | Both contexts, independent answers, savings or overhead, and actual tool traces |
| Durable notes | Add facts or run diagnostics; **Write notes & rotate**, or cross 80% automatically | Typed notes, exact source quotes, unchanged older entries, and W3 searching W1 |

Suggested prompts fill the composer; **Send** starts the live call. The diagnostic actually executes a faulty clock-offset calculation and multiplication checks. It is an intentional teaching component, not a recorded log or a simulated model response.

Use the inspector's arrows to browse earlier windows. Click a reduction's token delta for a side-by-side view of the original input and the seeds immediately after the transition. The visible chat remains on screen; it is **not** automatically replayed into the model after a reduction.

For the notes lab, run the diagnostic in W1, rotate, add a staging decision in W2, and rotate again. Ask why the fix failed in W3, then ask for its incidental marker. Carried notes should support the first answer; original-history search supplies the omitted marker. The **Tool trace** shows what actually happened.

### Why offloading can add tokens

A pointer has a fixed cost: IDs, a synopsis and retrieval arguments. Replacing a tiny source may therefore increase the request size. A long log can produce substantial savings. The app reports negative savings as overhead and retains both measured counts. A tool call is not required for offloading; source size and the replacement's size determine the result.

### What the token meter measures

Counts come from the [OpenAI input-token endpoint](https://developers.openai.com/api/docs/guides/token-counting), using the same model, instructions, tool schemas and input as generation. The default 6,000-token **application input budget** makes rollover visible. It is not a claim about the model's physical context capacity. Output has a separate 4,096-token allowance.

Blank sessions initially show “Not measured”; **Count active window** measures their envelope. Each completed chat refreshes the count. The Tool trace also reports usage returned by actual generation calls, including summary and note extraction calls. Live calls incur OpenAI API usage; this app does not estimate a bill.

## Implementation

```text
server.py                 FastAPI routes; local origin check; session locks
engine.py                 Responses loop, schema generation, reductions, notes
memory.py                 UTF-8 journals, immutable snapshots, scoped search
static/                   Educational pages, local SVG diagrams, chat and inspector
tests/test_memory.py      File, scope, integrity and tool-protocol checks
tests/live_check.py       Opt-in real OpenAI end-to-end validation
.data/                    Local session data; ignored by Git
```

Memory follows the notebook's layout:

```text
.data/memory/long_term/episodic/
  conversation/<session_id>/<window_id>/events.jsonl
  conversation/<session_id>/manifest.json
  summaries/<session_id>/<summary_id>.json
  offloaded_context/<session_id>/<offload_id>.json
  notes/<session_id>.txt
```

The notes are logically session-scoped working memory despite the shared `long_term/episodic` directory name. Journal records distinguish `original`, `seed` and `retrieval` items. Note extraction reads only fresh original user statements and work-tool outputs. It validates exact quoted evidence before committing notes.

All fitting notes are carried unchanged. If they outgrow their separate notes budget, the app carries recent full entries and older headlines generated at note creation. It never re-summarises stored notes. Literal Python search supplies older notes or original evidence, newest first. Archive search excludes the active window and derived copies. No shell, `grep`, embeddings or hidden semantic index is involved.

Before every model call, the loop counts the request. In the notes lab, exceeding 80% triggers extraction and rollover, including after a tool result. Completed action receipts prevent the next window from treating finished work as a new request. A second count stops a rollover whose notes and current request still exceed the threshold.

## Check it

Offline checks use real temporary files and actual Python calculations, with no mocked model:

```bash
python -m unittest discover -s tests -v
```

With the server running and a key configured, this creates fresh sessions and makes paid live calls:

```bash
python tests/live_check.py --live --url http://127.0.0.1:8877
```

The live checks cover deliberate summary loss, tool-pair offloading and exact recovery, accumulated notes, W3-to-W1 search, latest-user arbitration and mid-loop rollover. They save inspection session IDs under `.data/validation/`.

## Scope and limits

This implements the observable pattern from the [Astra release passage](https://openai.com/index/gpt-6-astra/). The typed note schema, filesystem layout, threshold, prompts and search policy are application choices, not disclosed Codex internals.

This is a single-process local learning app. Sessions are locked during mutations and manifests are atomically replaced, but journal, notes and manifest writes are not a single transaction. A process crash during a tool exchange needs recovery; the app stops rather than silently replaying an action. Very large inputs or tool results need ingestion limits or chunking in a production system. Search scans files and returns five literal matches; there is no automatic note consolidation, expiry or conflict invalidation.

Comparison branches use the same messages, model, selection rule and diagnostic marker, but separate model calls. Their answers and token usage can differ. A failed branch stays visible with its error; it is not replaced by a recorded answer.
