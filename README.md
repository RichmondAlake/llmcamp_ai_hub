# LLMCamp AI Hub

Hands-on lessons and applications from [LLMCamp](https://llmcamp.com) for agent
memory, context engineering, and System One decision models. Learn from short,
inspectable notebook cells, then explore the same experiments in local appbooks.

## Learning paths

| Technical content | Description | Link |
|---|---|---|
| Agent memory from scratch | Build an agent loop, lossy summaries, context offloading, durable notes, and searchable history. | [Notebook](agent_memory/agent_memory_from_scratch.ipynb) · [Open in Colab](https://colab.research.google.com/github/RichmondAlake/llmcamp_ai_hub/blob/main/agent_memory/agent_memory_from_scratch.ipynb) |
| MemoRizz with filesystem memory | Implement persistent notes, tool-result capture, and retrieval using filesystem storage. | [Notebook](agent_memory/persistent_notes_filesystem.ipynb) |
| MemoRizz with Oracle AI Database | Implement the memory patterns using Oracle AI Database as the memory provider. | [Notebook](agent_memory/persistent_notes_oracle.ipynb) |
| Agent Memory Appbook | Explore four interactive labs with live chat, context inspection, token counts, and architecture diagrams. | [Application & setup](agent_memory/appbook/README.md) |
| System One models from scratch | Six experiments with Jev, Oracle AI Database, Voyage and OpenAI: reranking, summary gates, routing, tools/skills, chunking, and Opus/Sol/Luna memory readers. | [Course & notebooks](system_one_models/README.md) |
| System One Appbook | Learn the experiments, inspect short code cells, run live comparisons and explore Oracle-backed charts and evidence. | [Application & setup](system_one_models/appbook/README.md) |

## Start the System One course

Begin with [Oracle setup](system_one_models/00_oracle_setup.ipynb), then follow the
[six-lesson guide](system_one_models/README.md). The lessons cover reranking, summary
quality gates, memory-use routing, tool/skill selection, semantic chunking, and
memory-reader comparisons. The notebooks build the experiments from scratch using
Python, SQL and HTTP, with saved outputs, pandas tables, diagrams and conclusions.
⭐ marks the main learning steps.

Use **Python 3.12**, **Docker Desktop**, and a local **Oracle AI Database**. From the
repository root:

```bash
cd system_one_models
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` with your Oracle passwords and provider keys: **TypeSafe Jev**, **Voyage AI**
and **OpenAI** for the main experiments; add **Anthropic** for the Opus/Sol/Luna reader
comparison. Interactive notebooks use hidden `getpass` prompts. The appbook reads keys
on the server. Then start the database and appbook:

```bash
docker compose up -d
docker compose ps
# Once Oracle is healthy:
python bootstrap_oracle.py
python appbook/server.py --port 8878
```

Open **http://127.0.0.1:8878**. The [setup guide](system_one_models/README.md#install-and-run-locally)
also explains how to reuse an existing Oracle instance. Run notebook cells in order
with the virtual environment as your VS Code or Jupyter kernel. Remote kernels need
a reachable database endpoint; their `localhost` is not your laptop.

The appbook provides:

- **Understand, Build it, Experiment:** use-case diagrams, reference architectures,
  notebook code and saved outputs, followed by live provider comparisons.
- **Live results:** charts update as results arrive; sortable tables explain metric
  definitions and expose evidence, latency, tokens and estimated API cost.
- **Configurable runs:** reranking and memory readers start with six questions and
  support up to **40 distinct labeled questions**. A full reranking run compares seven
  methods and produces **280 result rows**. Other lessons show their own dataset limits.
- **Oracle data explorer:** a collapsible, resizable panel for source tables, results,
  observed appbook reads/writes and transaction logs.

The appbook uses Oracle's `langchain-oracledb` integration for vector-table creation
and ingestion. The notebooks retain explicit SQL. Live calls incur provider usage;
the saved notebook outputs can be inspected without making new calls. The authored
datasets are small teaching examples, and their results are not a production leaderboard.

[Memorizz replication](system_one_models/README.md#replicate-the-reranking-test-in-memorizz)
exports frozen Oracle candidates for a new comparison. It requires the updated
Memorizz checkout described in the guide, which is maintained separately from this repository.

For the earlier agent-memory lessons, follow the setup instructions in their respective
notebooks or [appbook guide](agent_memory/appbook/README.md).

## Continue learning

- [Become an AI Memory Engineer](https://maven.com/ascxend/introduction-to-ai-agent-memory) (Maven course).
- [Explore 100 Days of Agent Memory](https://llmcamp.com/100days/agentmemory).
