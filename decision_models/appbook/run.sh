#!/usr/bin/env bash
# Launch the decision models appbook.
#
# Python, in order of preference:
#   1. $PYTHON, if you set it                       (PYTHON=/path/to/python ./run.sh)
#   2. ../.venv/bin/python, if it exists             (the notebooks' environment: torch, transformers, memorizz)
#   3. python3 on your PATH
# The notebooks' requirements must already be installed in that interpreter; the app's own
# (FastAPI, uvicorn, sse-starlette) are installed when an import check fails.
#
#   ./run.sh                     → http://127.0.0.1:8740
#   PORT=9000 ./run.sh           → another port
#   DM_PRELOAD=1 ./run.sh        → load d1-2B (about 7 GB) at start instead of on first use
set -euo pipefail

cd "$(dirname "$0")"

MODULE_VENV="../.venv/bin/python"
if [ -n "${PYTHON:-}" ]; then
  PY="$PYTHON"
elif [ -x "$MODULE_VENV" ]; then
  PY="$(cd "$(dirname "$MODULE_VENV")" && pwd)/python"
else
  PY="$(command -v python3 || command -v python)"
fi

(cd .. && "$PY" -c "import harness") 2>/dev/null \
  || { echo "The notebooks' harness does not import with $PY; install ../requirements.txt first."; exit 1; }
"$PY" -c "import fastapi, uvicorn, sse_starlette, memorizz, transformers" 2>/dev/null \
  || "$PY" -m pip install -q -r requirements.txt 2>/dev/null \
  || uv pip install -q --python "$PY" -r requirements.txt

HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8740}"
echo "→ Decision models appbook on http://${HOST}:${PORT}  (python: ${PY})"
exec "$PY" -m uvicorn backend.main:app --host "${HOST}" --port "${PORT}" "$@"
