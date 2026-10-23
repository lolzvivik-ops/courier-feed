"""
FastAPI server — backend for Кабинет (model app) and Пульт (owner app).

Endpoints are split by consumer:
  /model/…   — Кабинет iOS app
  /owner/…   — Пульт iOS app
  /internal/… — scheduler / worker callbacks

Run:
  uvicorn social_ios_automation.api.server:app --host 0.0.0.0 --port 8000
"""

import os
import time
import uuid
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Header, Request, status
from fastapi.middleware.cors import CORSMiddleware

from .routes import jobs, notifications, accounts

_API_KEY = os.getenv("API_SECRET_KEY", "changeme")


def _verify_key(x_api_key: Optional[str]) -> None:
    if not x_api_key or x_api_key != _API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup: verify DB connection
    try:
        from ..engine.db import execute
        execute("SELECT 1", fetch="one")
    except Exception as exc:
        import logging
        logging.getLogger("server").warning("DB not available at startup: %s", exc)
    yield
    # shutdown: nothing to teardown for now


app = FastAPI(
    title       = "Social Automation API",
    version     = "1.0.0",
    description = "Backend for Кабинет + Пульт iOS apps",
    lifespan    = lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins     = ["*"],
    allow_methods     = ["*"],
    allow_headers     = ["*"],
)

# ── request timing ───────────────────────────────────────────────────────────

@app.middleware("http")
async def add_timing(request: Request, call_next):
    start    = time.time()
    response = await call_next(request)
    ms       = int((time.time() - start) * 1000)
    response.headers["X-Response-Time"] = f"{ms}ms"
    return response


# ── health ────────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "ts": int(time.time())}


# ── routers ───────────────────────────────────────────────────────────────────

app.include_router(jobs.router,          prefix="/jobs",          tags=["jobs"])
app.include_router(notifications.router, prefix="/notifications", tags=["notifications"])
app.include_router(accounts.router,      prefix="/accounts",      tags=["accounts"])
