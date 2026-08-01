"""
Centralized logging configuration.

Configures the root logger with a console handler and a daily-rotating
on-disk file handler, both using either JSON or human-readable text
formatting depending on settings.LOG_FORMAT. Also propagates a per-request
correlation id (set by RequestContextLogMiddleware) into every log record
via a contextvar, and tames noisy third-party loggers (uvicorn, httpx,
sqlalchemy) so they don't duplicate or drown out our own log lines.
"""

import json
import logging
import os
from contextvars import ContextVar
from logging.handlers import TimedRotatingFileHandler

from app.core.config import settings

request_id_ctx_var: ContextVar[str | None] = ContextVar("request_id", default=None)

_LOG_RECORD_RESERVED_KEYS = set(logging.LogRecord("", 0, "", 0, "", None, None).__dict__.keys()) | {
    "message",
    "asctime",
}


class RequestIdFilter(logging.Filter):
    """Injects the current request's correlation id into every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_ctx_var.get() or "-"
        return True


class JsonFormatter(logging.Formatter):
    """Renders log records as single-line JSON objects."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", "-"),
        }

        extra = {
            key: value
            for key, value in record.__dict__.items()
            if key not in _LOG_RECORD_RESERVED_KEYS and key != "request_id"
        }
        if extra:
            payload.update(extra)

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, default=str)


_TEXT_FORMAT = "%(asctime)s %(levelname)-8s [%(request_id)s] %(name)s: %(message)s"


def _build_formatter() -> logging.Formatter:
    if settings.LOG_FORMAT == "json":
        return JsonFormatter()
    return logging.Formatter(_TEXT_FORMAT)


def configure_logging() -> None:
    """Configure the root logger. Call once, before the app is constructed."""
    formatter = _build_formatter()
    request_id_filter = RequestIdFilter()

    os.makedirs(settings.LOG_DIR, exist_ok=True)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.addFilter(request_id_filter)

    file_handler = TimedRotatingFileHandler(
        filename=os.path.join(settings.LOG_DIR, "app.log"),
        when="midnight",
        backupCount=14,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    file_handler.addFilter(request_id_filter)

    root_logger = logging.getLogger()
    root_logger.setLevel(settings.LOG_LEVEL)
    root_logger.handlers.clear()
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)

    # uvicorn.access is replaced by our own access-log middleware; httpx/httpcore
    # and sqlalchemy.engine are noisy at INFO/DEBUG and add little signal here.
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
