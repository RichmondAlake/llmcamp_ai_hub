"""Launch the cache lab on loopback; credentials stay in process memory."""
import argparse
import getpass
import os
from pathlib import Path

from dotenv import dotenv_values
import uvicorn

parser = argparse.ArgumentParser()
parser.add_argument("--port", type=int, default=8033)
parser.add_argument("--env-file", type=Path)
parser.add_argument("--ask-keys", action="store_true")
args = parser.parse_args()
private = dotenv_values(args.env_file) if args.env_file else {}
for name in ["ANTHROPIC_API_KEY", "TAVILY_API_KEY"]:
    value = None if args.ask_keys else os.getenv(name) or private.get(name)
    value = value or getpass.getpass(f"{name} (hidden): ").strip()
    if not value:
        raise ValueError(f"{name} is required")
    os.environ[name] = value
os.environ["NOTEBOOK_USE_ENV_KEYS"] = "1"
uvicorn.run("backend.main:app", host="127.0.0.1", port=args.port, access_log=False)
