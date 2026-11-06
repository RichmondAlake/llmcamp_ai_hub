"""Settings for the decision models appbook.

The app sits next to the notebooks and reuses their `harness/` package, so every decision here is
asked with the notebooks' own questions, sent the same way, and priced with the same rate card.
Keys come from the environment or an ignored `.env` (this folder first, then the notebooks' folder)
and never reach the browser.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

APP_DIR = Path(__file__).resolve().parent.parent          # .../decision_models/appbook
MODULE_DIR = APP_DIR.parent                               # .../decision_models (notebooks, harness, data)
FRONTEND_DIR = APP_DIR / "frontend"
NOTEBOOKS_DIR = MODULE_DIR / "notebooks"
NOTEBOOK_IMG_DIR = NOTEBOOKS_DIR / "img"                  # the notebooks' diagrams, served read-only at /img
DATA_DIR = APP_DIR / "data"                               # this app's session logs (gitignored)
DEFAULT_PORT = 8740

for candidate in (APP_DIR / ".env", MODULE_DIR / ".env"):
    if candidate.exists():
        load_dotenv(candidate, override=False)
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

if str(MODULE_DIR) not in sys.path:                       # `import harness`, exactly as the notebooks do
    sys.path.insert(0, str(MODULE_DIR))

#: The three decision models, in the order every page shows them.
BACKENDS = {
    "local": {"label": "d1", "maker": "Liquid AI", "model": "LiquidAI/d1-2B", "where": "this machine",
              "key": None, "color": "#199e70"},
    "jev": {"label": "Jev", "maker": "TypeSafe", "model": "jev-1.14.0", "where": "api.typesafe.ai/v1/systemone",
            "key": "TYPESAFE_API_KEY", "color": "#d55181"},
    "openai": {"label": "OpenAI Decisions", "maker": "OpenAI", "model": "gpt-6-luna",
               "where": "api.openai.com/v1/decisions", "key": "OPENAI_API_KEY", "color": "#d95926"},
}
#: The validated categorical order the notebooks use (harness/charts.py): typical blue, d1 aqua, gold yellow.
TYPICAL_COLOR = "#3987e5"
GOLD_COLOR = "#c98500"


class Settings:
    #: Load d1-2B when the server starts, instead of on the first local decision (about 7 GB).
    preload: bool = os.environ.get("DM_PRELOAD", "0") == "1"
    #: Delete a session's MemoRizz store and decision log on reset and on shutdown. Kept by default.
    cleanup: bool = os.environ.get("DM_CLEANUP", "0") == "1"
    #: Hosted requests in flight at once for a batch (the notebooks use eight).
    hosted_workers: int = int(os.environ.get("DM_HOSTED_WORKERS", "8"))


settings = Settings()
