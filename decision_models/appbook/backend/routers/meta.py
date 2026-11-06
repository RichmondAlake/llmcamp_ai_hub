"""Health, the lab session, and loading the local model."""
from __future__ import annotations

import harness
from fastapi import APIRouter

from backend.config import BACKENDS, DEFAULT_PORT, settings
from backend.core import models, session
from backend.core.swaps import common

router = APIRouter(prefix="/api", tags=["meta"])


@router.get("/health")
def health():
    s = session.current()
    return {"models": models.status(),
            "typical": {"llm": common.openai_ready(), "chat_model": harness.CHAT_MODEL,
                        "embedding_model": harness.EMBEDDING_MODEL},
            "session": {"id": s.id, "started": s.started, "decisions": len(s.calls), "store": s.store_path.name},
            "results": sorted(p.stem for p in harness.RESULTS.glob("[0-9][0-9]_*.jsonl")),
            "cleanup": settings.cleanup, "port": DEFAULT_PORT, "order": list(BACKENDS)}


@router.post("/models/local/load")
def load_local():
    if models.LOCAL["state"] not in ("loaded", "loading"):
        models.load_in_background()
    return models.status()["local"]


@router.get("/session")
def get_session():
    s = session.current()
    return {"id": s.id, "started": s.started, "decisions": len(s.calls), "last": s.last()}


@router.post("/session/reset")
def reset_session():
    s = session.reset()
    return {"id": s.id, "started": s.started, "kept": not settings.cleanup}
