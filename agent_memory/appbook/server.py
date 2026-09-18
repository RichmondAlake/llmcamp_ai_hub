"""Local-only appbook server. Run: python server.py --port 8877."""

from __future__ import annotations

import argparse
import os
import re
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from engine import DEFAULT_FOCUS, ROLLOVER_THRESHOLD, MemoryEngine
from memory import MemoryStore, uid

HERE = Path(__file__).resolve().parent
load_dotenv(os.getenv("APPBOOK_ENV_FILE", str(HERE / ".env")))
store = MemoryStore(os.getenv("APPBOOK_DATA_DIR", str(HERE / ".data")))
engine = MemoryEngine(store, os.getenv("OPENAI_API_KEY"))
app = FastAPI(title="LLMCAMP · Agent Memory Appbook", docs_url="/api/docs")


class SessionSettings(BaseModel):
    mode: Literal["summary", "offload", "notes"] = "summary"
    model: str = Field(default_factory=lambda: os.getenv("APPBOOK_MODEL", "gpt-6-astra"), min_length=1, max_length=100)
    effort: Literal["", "none", "low", "medium", "high"] = "low"
    budget: int = Field(default=6000, ge=3000, le=100000)
    notes_budget: int = Field(default=2400, ge=800, le=10000)
    diagnostic_checks: int = Field(default=120, ge=10, le=400)


class ChatRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=60000)


class ReduceRequest(BaseModel):
    focus: str = Field(default=DEFAULT_FOCUS, min_length=1, max_length=2000)
    tool_only: bool = False


class UpdateSettings(BaseModel):
    budget: int = Field(ge=3000, le=100000)
    auto_rollover: bool = True


@app.middleware("http")
async def local_origin(request: Request, call_next):
    origin = request.headers.get("origin")
    if request.method not in {"GET", "HEAD", "OPTIONS"} and origin:
        if origin != f"{request.url.scheme}://{request.headers.get('host')}":
            return JSONResponse({"detail": "Use this app from its own localhost page."}, status_code=403)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'"
    )
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response


def safe_error(error):
    # Never return authentication headers, credentials or server tracebacks to the UI.
    text = re.sub(r"sk-[A-Za-z0-9_\-]+", "[redacted]", str(error))
    return text[:800] or type(error).__name__


def present(state):
    result = store.public(state)
    schemas = [tool["schema"] for tool in engine.toolbox(state).values()]
    result["request_envelope"] = {key: value for key, value in
                                  engine.fields(state, [], schemas).items() if key != "input"}
    return result


def mutate(session_id, operation):
    try:
        lock = store.lock(session_id)
    except ValueError as error:
        raise HTTPException(400, "Invalid session ID.") from error
    if not lock.acquire(blocking=False):
        raise HTTPException(409, "This session is already working. Wait for the current action to finish.")
    state = None
    try:
        state = store.load(session_id)
        state["error"] = None
        operation(state)
        store.save(state)
        return present(state)
    except FileNotFoundError as error:
        raise HTTPException(404, safe_error(error)) from error
    except Exception as error:
        if state is not None:
            state["status"] = "Needs attention"
            state["error"] = safe_error(error)
            store.save(state)
        raise HTTPException(400 if isinstance(error, ValueError) else 502, safe_error(error)) from error
    finally:
        lock.release()


@app.get("/api/config")
def config():
    return {"ready": engine.client is not None,
            "model": os.getenv("APPBOOK_MODEL", "gpt-6-astra"),
            "effort": os.getenv("APPBOOK_REASONING_EFFORT", "low"),
            "threshold": ROLLOVER_THRESHOLD, "default_focus": DEFAULT_FOCUS}


@app.get("/api/sessions")
def list_sessions():
    rows = []
    for path in (store.root / "conversation").glob("*/manifest.json"):
        state = store.load(path.parent.name)
        rows.append({key: state[key] for key in
                     ("id", "mode", "model", "created_at", "updated_at", "group_id")}
                    | {"window_count": len(state["windows"]), "message_count": len(state["messages"])})
    return sorted(rows, key=lambda row: row["updated_at"], reverse=True)


@app.post("/api/sessions")
def create_session(settings: SessionSettings):
    state = store.create(**settings.model_dump())
    # Opening a blank session makes no paid generation request.
    return present(state)


@app.post("/api/comparisons")
def create_comparison(settings: SessionSettings):
    group_id, marker = uid(), "TRACE-" + uid()
    states = []
    for mode in ("summary", "offload"):
        values = settings.model_dump() | {"mode": mode, "group_id": group_id}
        state = store.create(**values)
        state["diagnostic_marker"] = marker
        store.save(state)
        states.append(present(state))
    return {"id": group_id, "sessions": states}


@app.get("/api/sessions/{session_id}")
def get_session(session_id: str):
    try:
        state = store.load(session_id)
        result = present(state)
        result["busy"] = store.lock(session_id).locked()
        return result
    except (FileNotFoundError, ValueError) as error:
        raise HTTPException(404, "Session not found.") from error


@app.post("/api/sessions/{session_id}/chat")
def chat(session_id: str, request: ChatRequest):
    if not request.prompt.strip():
        raise HTTPException(400, "Write a message first.")
    return mutate(session_id, lambda state: engine.chat(state, request.prompt))


@app.post("/api/sessions/{session_id}/reduce")
def reduce_context(session_id: str, request: ReduceRequest):
    return mutate(session_id, lambda state: engine.reduce(state, **request.model_dump()))


@app.post("/api/sessions/{session_id}/measure")
def measure(session_id: str):
    return mutate(session_id, engine.measure)


@app.patch("/api/sessions/{session_id}/settings")
def update_settings(session_id: str, request: UpdateSettings):
    def update(state):
        state.update(request.model_dump())
    return mutate(session_id, update)


@app.get("/api/sessions/{session_id}/search")
def search(session_id: str, query: str, target: Literal["notes", "session"] = "session"):
    try:
        return store.search(store.load(session_id), query, target)
    except (FileNotFoundError, ValueError) as error:
        raise HTTPException(400, safe_error(error)) from error


@app.get("/api/sessions/{session_id}/export")
def export_session(session_id: str):
    result = get_session(session_id)
    return JSONResponse(result, headers={"Content-Disposition": f'attachment; filename="memory-session-{session_id[:8]}.json"'})


@app.get("/resources/notebook")
def notebook():
    return FileResponse(HERE.parent / "agent_memory_from_scratch.ipynb", filename="agent_memory_from_scratch.ipynb")


@app.get("/")
def index():
    return FileResponse(HERE / "static" / "index.html")


app.mount("/static", StaticFiles(directory=HERE / "static"), name="static")


if __name__ == "__main__":
    import uvicorn
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8877)
    arguments = parser.parse_args()
    uvicorn.run(app, host="127.0.0.1", port=arguments.port, access_log=False)
