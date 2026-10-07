"""One error format for the whole API.

Every error response looks like:
    {"error": {"code": "NOT_FOUND", "message": "...", "request_id": "..."}}
Stack traces are never sent to the client.
"""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from snapclass.core.logging import request_id_var

logger = logging.getLogger(__name__)


class AppError(Exception):
    """Raise this anywhere in the app to return a clean error response."""

    def __init__(self, status_code: int, code: str, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


def not_found(what: str = "Resource") -> AppError:
    # We return 404 (not 403) for other people's data, so attackers cannot
    # even learn whether an id exists.
    return AppError(404, "NOT_FOUND", f"{what} not found")


def bad_request(message: str, code: str = "BAD_REQUEST") -> AppError:
    return AppError(400, code, message)


def conflict(message: str, code: str = "CONFLICT") -> AppError:
    return AppError(409, code, message)


def _error_body(code: str, message: str) -> dict:
    return {"error": {"code": code, "message": message, "request_id": request_id_var.get()}}


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content=_error_body(exc.code, exc.message))

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = {401: "UNAUTHORIZED", 403: "FORBIDDEN", 404: "NOT_FOUND", 405: "METHOD_NOT_ALLOWED"}
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_body(code.get(exc.status_code, "HTTP_ERROR"), str(exc.detail)),
            headers=getattr(exc, "headers", None),
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        # Build a short readable message such as "body.email: value is not a valid email".
        parts = []
        for err in exc.errors()[:3]:
            location = ".".join(str(item) for item in err.get("loc", []))
            parts.append(f"{location}: {err.get('msg')}")
        return JSONResponse(status_code=422, content=_error_body("VALIDATION_ERROR", "; ".join(parts)))

    @app.exception_handler(Exception)
    async def handle_unexpected_error(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled error")
        return JSONResponse(status_code=500, content=_error_body("INTERNAL_ERROR", "Something went wrong"))
