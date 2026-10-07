"""Liveness, readiness and Prometheus metrics endpoints."""

from fastapi import APIRouter
from fastapi.responses import JSONResponse, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy import text

from snapclass.core.db import engine
from snapclass.core.redis_client import get_redis

router = APIRouter(tags=["health"])


@router.get("/healthz")
def healthz() -> dict:
    """Liveness: the process is up."""
    return {"status": "ok"}


@router.get("/readyz")
def readyz() -> JSONResponse:
    """Readiness: the database and Redis can be reached."""
    checks = {}
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception:
        checks["database"] = "down"
    try:
        get_redis().ping()
        checks["redis"] = "ok"
    except Exception:
        checks["redis"] = "down"
    ready = all(value == "ok" for value in checks.values())
    return JSONResponse(status_code=200 if ready else 503, content=checks)


@router.get("/metrics")
def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
