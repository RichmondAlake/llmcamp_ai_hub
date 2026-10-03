"""Execute the cache notebooks end to end against real providers and save their outputs in place.

    python tests/run_notebooks.py --env-file ~/.private/keys.env 01 03
    python tests/run_notebooks.py --env-file ~/.private/keys.env        # all six

Run it with the Python environment that has requirements.txt installed: the notebook kernel
uses that interpreter. Provider keys come from --env-file (only ANTHROPIC_API_KEY and
TAVILY_API_KEY are read) or the environment; the notebooks read them because the runner sets
NOTEBOOK_USE_ENV_KEYS=1. Oracle settings come from ORACLE_USER/ORACLE_PASSWORD/ORACLE_DSN or
--oracle-json, and the True Cache pair from TRUE_CACHE_USER/TRUE_CACHE_PASSWORD/PRIMARY_DSN/
TRUE_CACHE_DSN or --true-cache-json. Every cell runs, including the %pip install cell.

A passing run saves the outputs into the notebook itself. A failed run leaves the notebook
unchanged and saves the partial run to the system temporary folder. Outputs are checked for
key and password values before anything is written.
"""
import argparse
import json
import os
import re
import sys
import tempfile
import time
from pathlib import Path

import nbformat
from dotenv import dotenv_values
from nbclient import NotebookClient
from nbclient.exceptions import CellExecutionError

ROOT = Path(__file__).resolve().parents[1]
KEYS = ["ANTHROPIC_API_KEY", "TAVILY_API_KEY"]


def prepare_environment(args):
    private = dotenv_values(args.env_file) if args.env_file else {}
    for name in KEYS:
        if private.get(name):
            os.environ[name] = private[name]
    for path, marker in [(args.oracle_json, "ORACLE_USER"), (args.true_cache_json, "TRUE_CACHE_USER")]:
        if path and path.exists() and not os.getenv(marker):
            os.environ.update(json.loads(path.read_text()))
    os.environ["NOTEBOOK_USE_ENV_KEYS"] = "1"
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
    return [os.environ[name] for name in KEYS + ["ORACLE_PASSWORD", "TRUE_CACHE_PASSWORD"] if os.getenv(name)]


def scrub(text, secrets):
    text = re.sub(r"\x1b\[[0-9;]*m", "", text)
    for value in secrets:
        text = text.replace(value, "[redacted]")
    return text


def execute(path, secrets):
    notebook = nbformat.read(path, as_version=4)
    client = NotebookClient(notebook, timeout=1800, kernel_name="python3",
                            resources={"metadata": {"path": str(ROOT)}})
    started, error = time.perf_counter(), None
    with client.setup_kernel():
        try:
            for index, cell in enumerate(notebook.cells):
                if cell.cell_type == "code":
                    client.execute_cell(cell, index)
        except CellExecutionError as exc:
            error = scrub(str(exc), secrets)[-4000:]
    text = nbformat.writes(notebook)
    if any(value in text for value in secrets):
        error = (error or "") + "\nA private key value appeared in the outputs; nothing was saved."
        text = scrub(text, secrets)
    executed = sum(1 for c in notebook.cells if c.cell_type == "code" and c.get("execution_count"))
    return text, round(time.perf_counter() - started, 1), executed, error


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("prefixes", nargs="*", help="notebook name prefixes, e.g. 01 06")
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--oracle-json", type=Path, default=ROOT / "appbook/data/oracle.json")
    parser.add_argument("--true-cache-json", type=Path, default=ROOT / "appbook/data/true_cache.json")
    args = parser.parse_args()
    secrets = prepare_environment(args)
    paths = sorted(ROOT.glob("0[1-6]_*.ipynb"))
    paths = [p for p in paths if not args.prefixes or any(p.name.startswith(x) for x in args.prefixes)]
    failures = 0
    for path in paths:
        print(f"{path.name}: running …", flush=True)
        text, seconds, executed, error = execute(path, secrets)
        if error:
            failures += 1
            partial = Path(tempfile.gettempdir()) / path.name.replace(".ipynb", ".failed.ipynb")
            partial.write_text(text)
            print(f"{path.name}: FAILED after {seconds}s; partial notebook: {partial}\n{error}")
        else:
            path.write_text(text)
            print(f"{path.name}: passed in {seconds}s, {executed} code cells")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
