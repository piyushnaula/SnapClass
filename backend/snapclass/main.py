"""FastAPI app: routers, error handlers, request-id + logging + metrics middleware.

Run with:  uvicorn snapclass.main:app --reload
"""

import logging
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import Counter, Histogram

from snapclass.api.routers import admin, auth, classes, health, join, media, sessions, students
from snapclass.core.config import settings
from snapclass.core.errors import register_error_handlers
from snapclass.core.logging import request_id_var, setup_logging, user_id_var

logger = logging.getLogger("snapclass.request")

REQUEST_COUNT = Counter("http_requests_total", "HTTP requests", ["method", "route", "status"])
REQUEST_LATENCY = Histogram("http_request_duration_seconds", "HTTP request latency", ["method", "route"])


def create_app() -> FastAPI:
    setup_logging()
    app = FastAPI(title="SnapClass API", version="2.0.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    )

    @app.middleware("http")
    async def request_context(request: Request, call_next):  # noqa: ANN001, ANN202
        # Reuse the caller's request id if it looks safe, otherwise make a new one.
        incoming = request.headers.get("x-request-id", "")
        request_id = incoming if 0 < len(incoming) <= 64 and incoming.replace("-", "").isalnum() else uuid.uuid4().hex
        request_id_var.set(request_id)
        user_id_var.set("-")

        started = time.perf_counter()
        response = await call_next(request)
        elapsed = time.perf_counter() - started

        # Use the route template (/sessions/{session_id}), not the real path, to keep metrics small.
        route = getattr(request.scope.get("route"), "path", "unmatched")
        REQUEST_COUNT.labels(request.method, route, response.status_code).inc()
        REQUEST_LATENCY.labels(request.method, route).observe(elapsed)
        response.headers["X-Request-ID"] = request_id
        if route not in ("/healthz", "/metrics"):
            logger.info(
                "request",
                extra={
                    "fields": {
                        "method": request.method,
                        "route": route,
                        "status": response.status_code,
                        "latency_ms": round(elapsed * 1000, 1),
                    }
                },
            )
        return response

    register_error_handlers(app)

    app.include_router(health.router)
    for router in (
        auth.router,
        admin.router,
        classes.router,
        join.router,
        students.router,
        sessions.router,
        media.router,
    ):
        app.include_router(router, prefix="/api/v1")
    return app


app = create_app()
