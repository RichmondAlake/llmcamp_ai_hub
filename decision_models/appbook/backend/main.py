"""The decision models appbook: FastAPI backend and static frontend on one origin.

Run from the `appbook/` directory:
    ./run.sh            # http://127.0.0.1:8740
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.config import DEFAULT_PORT, FRONTEND_DIR, NOTEBOOK_IMG_DIR, settings
from backend.core import models, session
from backend.routers import data_explorer, decisions, meta, reference, tokenomics


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.preload:
        models.load_in_background()          # DM_PRELOAD=1: d1-2B loads while the first page opens
    yield
    session.current().close()                # deletes the session's store and log only when DM_CLEANUP=1


app = FastAPI(title="Decision Models Appbook", version="1.0.0", lifespan=lifespan)


@app.exception_handler(Exception)
async def unexpected(request, exc):
    return JSONResponse({"detail": f"{type(exc).__name__}: {exc}".splitlines()[0][:300]}, status_code=500)


@app.middleware("http")
async def revalidate_frontend(request, call_next):
    response = await call_next(request)
    if not request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-cache"
    return response


for r in (meta.router, reference.router, decisions.router, tokenomics.router, data_explorer.router):
    app.include_router(r)
if NOTEBOOK_IMG_DIR.exists():
    app.mount("/img", StaticFiles(directory=str(NOTEBOOK_IMG_DIR)), name="img")
app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("backend.main:app", host="127.0.0.1", port=DEFAULT_PORT, reload=False)
