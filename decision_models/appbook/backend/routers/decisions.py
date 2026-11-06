"""The seven swap pages, and the playground.

Every swap has the same three endpoints: describe it, try one input through today's method and the
chosen decision models, and run the notebook's labelled set through one decision model, streaming
progress as server-sent events.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.core import models, session, sse
from backend.core.swaps import BY_ID, cache, catalog, consolidation, describe, items, scorer
from backend.core.swaps import common
from backend.schemas import Playground, RunLabelled, TrySwap

router = APIRouter(prefix="/api", tags=["swaps"])


def _module(swap_id: str):
    if swap_id not in BY_ID:
        raise HTTPException(404, f"No swap called {swap_id!r}.")
    return BY_ID[swap_id]


def _backends(requested) -> list[str]:
    return models.wanted(requested)


@router.get("/swaps")
def swaps():
    return {"swaps": catalog()}


@router.get("/swaps/{swap_id}")
def swap(swap_id: str):
    return describe(_module(swap_id))


@router.post("/swaps/{swap_id}/try")
def try_swap(swap_id: str, req: TrySwap):
    module = _module(swap_id)
    if module is consolidation:
        if not (req.stored and req.new):
            raise HTTPException(422, "Give a stored memory and a new one.")
        value = {"stored": req.stored, "new": req.new}
    else:
        value = (req.text or "").strip()
        if not value:
            raise HTTPException(422, "Type something to try.")
    backends = _backends(req.backends)
    if not backends and not common.openai_ready():
        raise HTTPException(503, "Nothing can answer: no decision model is available and OPENAI_API_KEY is not set.")
    try:
        return module.try_(session.current(), value, backends)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post("/swaps/{swap_id}/run")
def run_swap(swap_id: str, req: RunLabelled):
    module = _module(swap_id)
    if not models.available(req.backend):
        raise HTTPException(503, f"{models.label(req.backend)} is not available: {models.status()[req.backend]['state']}")
    s = session.current()

    def work(progress):
        progress(0, 1, stage="preparing the labelled set")
        prepared = items(module, s)
        result = common.labelled_run(s, swap_id, req.backend, prepared, scorer(module, s), progress)
        result["notebook"] = describe(module)["scorecard"]
        return result

    return sse.stream(work)


@router.get("/swaps/cache/trap")
def cache_trap():
    if not common.openai_ready():
        raise HTTPException(503, "The threshold sweep needs OPENAI_API_KEY for embeddings.")
    return cache.trap()


@router.get("/swaps/consolidation/dots")
def consolidation_dots():
    if not common.openai_ready():
        raise HTTPException(503, "The similarity chart needs OPENAI_API_KEY for embeddings.")
    return consolidation.dots()


# ── any question: the playground ─────────────────────────────────────────
@router.post("/playground")
def playground(req: Playground):
    from harness import d1

    questions = {}
    for q in req.questions:
        if q.type == "noul":
            questions[q.name] = d1.noul(q.instructions, q.true, q.false)
        elif q.type == "choice":
            if not q.options:
                raise HTTPException(422, f"{q.name}: a choice needs options")
            questions[q.name] = d1.choice(q.instructions, q.options)
        else:
            if not q.levels:
                raise HTTPException(422, f"{q.name}: a score needs levels")
            questions[q.name] = d1.score(q.instructions, q.levels)
    if len(questions) != len(req.questions):
        raise HTTPException(422, "Question names must be unique.")
    backends = _backends(req.backends)
    if not backends:
        raise HTTPException(503, "No decision model is available: d1 failed to load and no Jev or OpenAI key is set.")
    s = session.current()
    records = models.ask_all(backends, req.state, questions)
    entry = s.record("playground", records, summary=req.state)
    return {"results": records, "questions": questions, "entry": entry["n"]}
