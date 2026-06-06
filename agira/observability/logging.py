"""Structured JSON logging with demo/debug modes and span tracking."""

from __future__ import annotations

import json
import logging
import sys
import uuid
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any

trace_id_var: ContextVar[str] = ContextVar("trace_id", default="")
span_id_var: ContextVar[str] = ContextVar("span_id", default="")
log_mode_var: ContextVar[str] = ContextVar("log_mode", default="demo")


def new_trace_id() -> str:
    return str(uuid.uuid4())


def new_span_id() -> str:
    return str(uuid.uuid4())[:12]


def get_trace_id() -> str:
    tid = trace_id_var.get()
    if not tid:
        tid = new_trace_id()
        trace_id_var.set(tid)
    return tid


def set_trace_id(trace_id: str) -> None:
    trace_id_var.set(trace_id)


def set_log_mode(mode: str) -> None:
    log_mode_var.set(mode)


def get_log_mode() -> str:
    return log_mode_var.get() or "demo"


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "trace_id": get_trace_id(),
            "span_id": span_id_var.get() or None,
        }
        if hasattr(record, "extra_fields"):
            payload.update(record.extra_fields)  # type: ignore[attr-defined]
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def setup_logging(level: int = logging.INFO) -> logging.Logger:
    logger = logging.getLogger("agira")
    logger.handlers.clear()
    if get_log_mode() == "debug":
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)
        logger.setLevel(level)
    else:
        logger.addHandler(logging.NullHandler())
        logger.setLevel(logging.CRITICAL + 1)
    logger.propagate = False
    return logger


def log_event(
    logger: logging.Logger,
    event: str,
    *,
    level: int = logging.INFO,
    **fields: Any,
) -> dict[str, Any]:
    entry = {"event": event, "trace_id": get_trace_id(), "span_id": span_id_var.get(), **fields}
    if get_log_mode() == "debug":
        record = logger.makeRecord(logger.name, level, "(agira)", 0, event, (), None)
        record.extra_fields = entry  # type: ignore[attr-defined]
        logger.handle(record)
    return entry


def demo_print(msg: str) -> None:
    if get_log_mode() == "demo":
        print(msg)
