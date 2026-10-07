"""JSON logging with a request id on every line."""

import json
import logging
import sys
from contextvars import ContextVar
from datetime import UTC, datetime

# Context variables hold per-request values. Each request (or job) sees its own copy.
request_id_var: ContextVar[str] = ContextVar("request_id", default="-")
user_id_var: ContextVar[str] = ContextVar("user_id", default="-")


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        data = {
            "time": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": request_id_var.get(),
            "user_id": user_id_var.get(),
        }
        # Extra fields passed with logger.info("...", extra={"fields": {...}})
        fields = getattr(record, "fields", None)
        if isinstance(fields, dict):
            data.update(fields)
        if record.exc_info:
            data["exception"] = self.formatException(record.exc_info)
        return json.dumps(data, default=str)


def setup_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)
    # uvicorn's access log duplicates our request log, so silence it.
    logging.getLogger("uvicorn.access").disabled = True
