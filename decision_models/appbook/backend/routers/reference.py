"""The reference architecture and the notebooks' saved results."""
from __future__ import annotations

from fastapi import APIRouter

from backend.core import architecture, evidence

router = APIRouter(prefix="/api", tags=["reference"])


@router.get("/architecture")
def reference():
    return architecture.reference()


@router.get("/evidence/scoreboard")
def scoreboard():
    return {"swaps": evidence.scoreboard()}


@router.get("/evidence/providers")
def providers():
    return evidence.providers()


@router.post("/evidence/reload")
def reload():
    evidence.clear()
    return {"ok": True}
