"""Shared harness for the decision model notebooks: paths, keys and the runtime guards.

The notebooks import from here so each one stays short and every swap is measured the same way.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

# FAISS and PyTorch each bring an OpenMP runtime on macOS. Without this the process can abort
# the moment both are loaded.
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
os.environ.setdefault("RAGAS_DO_NOT_TRACK", "true")

# Saved notebook outputs should hold results, not library noise: no progress bars, no advisory
# warnings, and no import-time notes. VS Code does not wrap output, so long noise lines get cut off.
import logging  # noqa: E402
import warnings  # noqa: E402

os.environ.setdefault("TQDM_DISABLE", "1")
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")
os.environ.setdefault("HF_HUB_VERBOSITY", "error")
warnings.filterwarnings("ignore", message=r".*langchain-experimental.*")
warnings.filterwarnings("ignore", message=r"IProgress not found")
logging.getLogger("torch.distributed.elastic.multiprocessing.redirects").setLevel(logging.ERROR)
logging.getLogger("huggingface_hub").setLevel(logging.ERROR)

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
RESULTS = ROOT / "results"
STORE = ROOT / "memory_store"

CHAT_MODEL = os.environ.get("CHAT_MODEL", "gpt-4o-mini")
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSIONS = 256

#: Rank recall on relevance alone. Everything in these stores was written in the same second, so
#: recency carries no signal, and memorizz min-max normalises it across candidates: a difference
#: of milliseconds becomes the whole 0 to 1 range and the oldest chunk scores lowest.
RELEVANCE_ONLY = {"alpha_recency": 0.0, "alpha_importance": 0.0}


def load_env() -> list[str]:
    """Read ROOT/.env and return the names of the keys that are set, never their values."""
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env", override=False)
    names = ("OPENAI_API_KEY", "LIQUID_API_KEY", "TYPESAFE_API_KEY", "HF_TOKEN")
    return [name for name in names if os.environ.get(name)]


def demo() -> tuple[str, dict]:
    """The transcript and its gold topics, the same input in every notebook."""
    text = (DATA / "demo_text.md").read_text(encoding="utf-8")
    return text, json.loads((DATA / "demo_text.json").read_text(encoding="utf-8"))


def labels(name: str) -> dict:
    """One of data/labels_*.json: cache, memory_routing, dedup, extraction or tools."""
    return json.loads((DATA / f"labels_{name}.json").read_text(encoding="utf-8"))


def eval_questions() -> list[dict]:
    """The 40 questions with gold excerpts and their character spans."""
    return json.loads((DATA / "eval_questions.json").read_text(encoding="utf-8"))["questions"]


def save_chunks(name: str, rows: list[dict]) -> None:
    """Write results/chunks_<name>.json as a list of {"text", "start", "end"}."""
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / f"chunks_{name}.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")


def load_chunks(name: str) -> list[dict]:
    return json.loads((RESULTS / f"chunks_{name}.json").read_text(encoding="utf-8"))
