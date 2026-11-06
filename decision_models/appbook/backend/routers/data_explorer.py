"""The Data Explorer drawer: read-only, allowlisted, paged. No query language is accepted."""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException, Query

from backend.core import explorer, session

router = APIRouter(prefix="/api/data_explorer", tags=["data explorer"])
Scope = Literal["session", "all"]


@router.get("/tables")
def tables(scope: Scope = "session"):
    s = session.current()
    return {"tables": explorer.catalogue(s, scope), "session": s.id, "scope": scope}


@router.get("/tables/{name}/rows")
def rows(name: str, scope: Scope = "session", offset: int = Query(0, ge=0), limit: int = Query(40, ge=1, le=100)):
    if name not in explorer.TABLES:
        raise HTTPException(404, f"{name} is not an explorer table")
    return explorer.page(name, session.current(), scope, offset, limit)


@router.get("/activity")
def activity():
    return {"activity": list(session.current().activity)}
