"""Loopback API for real cache comparisons and measured experiments."""
import json
import os
import threading
import uuid
from contextlib import asynccontextmanager
from datetime import date, datetime
from pathlib import Path
from typing import Literal

import numpy as np
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

ROOT = Path(__file__).resolve().parents[1]
for private in ["data/oracle.json", "data/true_cache.json"]:
    if (ROOT / private).exists():
        for name, value in json.loads((ROOT / private).read_text()).items():
            os.environ.setdefault(name, value)
from . import service as s
from . import experiments as e


def safe(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [safe(item) for item in value]
    if isinstance(value, np.generic):
        return value.item()
    return value


@asynccontextmanager
async def lifespan(app):
    threading.Thread(target=s.warm, daemon=True).start()
    yield
    with s.lock:
        if s.core:
            s.core.client.close()
            for conn in [s.core.conn, s.core.primary, s.core.true_cache]:
                conn.close()


app = FastAPI(title="Cachecraft · measured cache techniques", lifespan=lifespan)


@app.middleware("http")
async def origin_check(request: Request, call_next):
    origin = request.headers.get("origin")
    if request.method not in {"GET", "HEAD", "OPTIONS"} and origin and origin != "http://" + request.headers.get("host", ""):
        return JSONResponse({"detail": "Cross-origin writes are not accepted"}, status_code=403)
    return await call_next(request)


@app.exception_handler(Exception)
@app.exception_handler(ValueError)
@app.exception_handler(RuntimeError)
async def failed(request, exc):
    return JSONResponse({"detail": s.scrub(exc)}, status_code=409)


class Features(BaseModel):
    model_config = ConfigDict(extra="forbid")
    normal: bool = True
    embedding: bool = True
    semantic: bool = True
    prompt: bool = True
    tool: bool = True


class Config(BaseModel):
    model_config = ConfigDict(extra="forbid")
    revision: str = Field(default="v1", min_length=1, max_length=80)
    ttl: float = Field(default=300, ge=0.1, le=3600)
    tool_ttl: float = Field(default=60, ge=0.1, le=300)
    threshold: float = Field(default=0.10, ge=0, le=0.6)
    rerank_min: float = Field(default=0.0, ge=-12, le=12)
    depth: Literal["basic", "advanced"] = "basic"
    max_results: int = Field(default=3, ge=1, le=5)
    features: Features = Field(default_factory=Features)


class Comparison(BaseModel):
    query: str = Field(min_length=1, max_length=4000)
    kind: Literal["explanation", "live"] = "explanation"
    role: Literal["query", "document"] | None = None
    config: Config = Field(default_factory=Config)


class WorkloadInput(BaseModel):
    mode: Literal["scenario", "synthetic", "custom"] = "scenario"
    scenario: Literal["repeat", "mixed", "diverse", "invalidation"] = "mixed"
    turns: int = Field(default=6, ge=1, le=30)
    focus: str = Field(default="", max_length=1500)
    live_query: str = Field(default="Oracle AI Database HNSW vector search official documentation", min_length=1, max_length=4000)
    requests: list[dict] = Field(default_factory=list, max_length=30)


class VectorSpace(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str = Field(default="", max_length=1000)
    add: list[str] = Field(default_factory=list, max_length=20)
    clear: bool = False
    load_examples: bool = False
    threshold: float = Field(default=0.10, ge=0, le=0.6)
    rerank_min: float = Field(default=0.0, ge=-12, le=12)


class Experiment(BaseModel):
    workload_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    comparison: Literal["cumulative", "individual", "custom"] = "cumulative"
    config: Config = Field(default_factory=Config)


workloads = {}


@app.get("/api/status")
def status():
    return {"ready": s.ready, "error": s.error, "model": s.c.MODEL, "embedding_model": s.c.EMBED_MODEL,
            "reranker_model": s.c.RERANK_MODEL, "embedding_dimensions": s.c.EMBED_DIM,
            "true_cache": {"primary": os.getenv("PRIMARY_DSN"), "reads": os.getenv("TRUE_CACHE_DSN")},
            "oracle": "connected" if s.ready else "warming", "pricing_date": s.c.PRICE_DATE,
            "workspace": s.core.workspace if s.ready else None,
            "shared_setup": s.core.startup if s.ready else None}


@app.post("/api/compare/{mechanism}")
def compare(mechanism: str, payload: Comparison):
    if mechanism not in s.MECHANISMS:
        raise HTTPException(404, "Unknown caching technique")
    with s.lock:
        return safe(s.require().compare(mechanism, payload.model_dump()))


@app.post("/api/reset/{mechanism}")
def reset(mechanism: str):
    if mechanism not in s.MECHANISMS:
        raise HTTPException(404, "Unknown caching technique")
    with s.lock:
        return s.require().reset(mechanism)


@app.get("/api/history/{mechanism}")
def history(mechanism: str):
    with s.lock:
        return safe([row for row in s.require().history if row["mechanism"] == mechanism])


@app.get("/api/tables")
def tables():
    """Read-only data explorer: the app's Oracle tables and their row counts."""
    with s.lock:
        return safe(s.require().explorer_tables())


@app.get("/api/tables/{name}")
def table(name: str):
    if name not in s.EXPLORER:
        raise HTTPException(404, "Unknown table")
    with s.lock:
        return safe(s.require().explorer_rows(name))


@app.post("/api/vector-space")
def vector_space(payload: VectorSpace):
    """Cached and example questions in 3D (PCA), plus the cache policy's verdict for a query."""
    with s.lock:
        return safe(s.require().vector_space(**payload.model_dump()))


@app.post("/api/sandbox")
def sandbox():
    with s.lock:
        if e.active():
            raise ValueError("Finish or stop the running experiment before starting a new sandbox")
        core = s.require()
        core.workspace, core.lanes, core.history = uuid.uuid4().hex, {}, []
        core.resets = {name: 0 for name in s.MECHANISMS}
        core.save_workspace()
        core.save_history()
        return {"workspace": core.workspace}


@app.post("/api/workloads")
def workload(payload: WorkloadInput):
    with s.lock:
        value = e.prepare(payload.model_dump())
        workloads[value["id"]] = value
        return safe(value)


@app.post("/api/tokenomics")
def experiment(payload: Experiment):
    with s.lock:
        if payload.workload_id not in workloads:
            raise ValueError("Preview a workload first")
        return safe(e.start(payload.model_dump() | {"workload": workloads[payload.workload_id]}))


@app.get("/api/tokenomics")
def experiments():
    return safe(e.recent())


@app.get("/api/tokenomics/{job_id}")
def job(job_id: str):
    if len(job_id) != 32 or any(char not in "0123456789abcdef" for char in job_id):
        raise HTTPException(404, "Experiment not found")
    try:
        return safe(e.get(job_id))
    except FileNotFoundError:
        raise HTTPException(404, "Experiment not found")


@app.post("/api/tokenomics/{job_id}/cancel")
def cancel(job_id: str):
    e.get(job_id)
    with e.job_lock:
        if job_id not in e.jobs or e.jobs[job_id]["status"] != "running":
            raise ValueError("This experiment is no longer running")
        e.jobs[job_id]["cancel_requested"] = True
    return {"id": job_id, "cancel_requested": True}


app.mount("/", StaticFiles(directory=ROOT / "frontend", html=True), name="frontend")
