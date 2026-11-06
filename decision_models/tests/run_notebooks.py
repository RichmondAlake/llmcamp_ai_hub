"""Run notebooks top to bottom and save the outputs into the same .ipynb.

    .venv/bin/python tests/run_notebooks.py            # all of them
    .venv/bin/python tests/run_notebooks.py 02 04      # only these

HF_HUB_OFFLINE=1 is set, so the run proves the cached weights are enough. A notebook that fails
stops the run, and its partial outputs are saved so the failing cell can be read.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import nbformat
from nbclient import NotebookClient
from nbclient.exceptions import CellExecutionError

ROOT = Path(__file__).resolve().parents[1]
NOTEBOOKS = ROOT / "notebooks"
KERNEL = "decision-models"


def run(path: Path) -> float:
    nb = nbformat.read(path, as_version=4)
    client = NotebookClient(nb, timeout=None, kernel_name=KERNEL,
                            resources={"metadata": {"path": str(NOTEBOOKS)}})
    started = time.perf_counter()
    try:
        client.execute()
    finally:
        nbformat.write(nb, path)
    return time.perf_counter() - started


def main() -> int:
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    picks = sys.argv[1:]
    paths = sorted(p for p in NOTEBOOKS.glob("[0-9][0-9]_*.ipynb")
                   if not picks or p.name[:2] in picks)
    total = 0.0
    for path in paths:
        print(f"{path.name} ...", flush=True)
        try:
            seconds = run(path)
        except CellExecutionError as error:
            print(f"FAILED {path.name}\n{str(error)[-1500:]}", flush=True)
            return 1
        total += seconds
        print(f"  ok in {seconds:.0f} s", flush=True)
    print(f"all passed in {total:.0f} s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
