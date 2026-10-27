import logging
import time
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Annotated

import psycopg
from fastapi import FastAPI, HTTPException, Path, Query, Request, Response
from fastapi.responses import JSONResponse
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from pydantic import BaseModel, ConfigDict, Field
from app.db import create_pool

logger = logging.getLogger("app")

BIGINT_MAX = 9223372036854775807


@asynccontextmanager
async def lifespan(app: FastAPI):
    pool = create_pool()
    pool.open(wait=False) 
    app.state.pool = pool
    try:
        yield
    finally:
        pool.close()


app = FastAPI(title="notes", lifespan=lifespan)


REQUESTS = Counter("http_requests_total", "Количество HTTP-запросов", ["method", "path", "status"])
DURATION = Histogram(
    "http_request_duration_seconds", "Длительность HTTP-запросов", ["method", "path"]
)
UNTRACKED_PATHS = {"/healthz", "/readyz", "/metrics"}


@app.middleware("http")
async def track_metrics(request: Request, call_next):
    if request.url.path in UNTRACKED_PATHS:
        return await call_next(request)
    start = time.perf_counter()
    status = 500
    try:
        response = await call_next(request)
        status = response.status_code
        return response
    finally:
        route = request.scope.get("route")
        path = route.path if route else "unmatched"
        DURATION.labels(request.method, path).observe(time.perf_counter() - start)
        REQUESTS.labels(request.method, path, str(status)).inc()


@app.exception_handler(psycopg.OperationalError)
async def database_unavailable(request: Request, exc: psycopg.OperationalError):
    """БД недоступна или пул исчерпан: честный 503 вместо 500 с трассировкой."""
    logger.error("БД недоступна: %s", exc)
    return JSONResponse(status_code=503, content={"detail": "database unavailable"})


class NoteIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    text: str = Field(min_length=1, max_length=1000)


class NoteOut(BaseModel):
    id: int
    text: str
    created_at: datetime


@app.post("/notes", response_model=NoteOut, status_code=201)
def create_note(note: NoteIn, request: Request):
    with request.app.state.pool.connection() as conn:
        row = conn.execute(
            "INSERT INTO notes (text) VALUES (%s) RETURNING id, text, created_at",
            (note.text,),
        ).fetchone()
    return row


@app.get("/notes", response_model=list[NoteOut])
def list_notes(request: Request, limit: Annotated[int, Query(ge=1, le=200)] = 50):
    with request.app.state.pool.connection() as conn:
        rows = conn.execute(
            "SELECT id, text, created_at FROM notes ORDER BY id DESC LIMIT %s",
            (limit,),
        ).fetchall()
    return rows


@app.get("/notes/{note_id}", response_model=NoteOut)
def get_note(request: Request, note_id: Annotated[int, Path(ge=1, le=BIGINT_MAX)]):
    with request.app.state.pool.connection() as conn:
        row = conn.execute(
            "SELECT id, text, created_at FROM notes WHERE id = %s", (note_id,)
        ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="note not found")
    return row


@app.get("/healthz")
def healthz():
    """Liveness: процесс жив. БД не проверяем: перезапуск пода БД не починит."""
    return {"status": "ok"}


@app.get("/readyz")
def readyz(request: Request):
    """Readiness: можно ли слать трафик. Нужна доступная БД."""
    try:
        with request.app.state.pool.connection(timeout=2) as conn:
            conn.execute("SELECT 1")
    except psycopg.Error as exc:
        logger.warning("readyz: БД недоступна: %s", exc)
        return JSONResponse(status_code=503, content={"status": "database unavailable"})
    return {"status": "ready"}


@app.get("/metrics", include_in_schema=False)
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
