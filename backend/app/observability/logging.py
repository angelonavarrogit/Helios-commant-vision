"""Structured JSON logging with secret redaction.

Every log record is emitted as a single JSON line including a timestamp, level,
logger name and message, plus any structured `extra` fields. Sensitive values
are redacted defensively so secrets never reach the logs (RNF-04, security.md).
"""

from __future__ import annotations

import json
import logging
import re
import sys
from typing import Any

# Keys whose values must never be logged in clear text.
_SENSITIVE_KEY_PATTERN = re.compile(
    r"(token|secret|password|api_key|apikey|authorization|client_secret|"
    r"encryption_key|credential|cookie)",
    re.IGNORECASE,
)

_REDACTED = "***REDACTED***"

# Reserved LogRecord attributes we do not want to duplicate into `extra`.
_RESERVED_LOG_ATTRS = frozenset(vars(logging.makeLogRecord({})).keys() | {"message", "asctime"})


def _redact(key: str, value: Any) -> Any:
    """Redact a value if its key looks sensitive."""
    if _SENSITIVE_KEY_PATTERN.search(key):
        return _REDACTED
    return value


class JsonFormatter(logging.Formatter):
    """Format log records as compact JSON lines with redaction."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Include structured extras (request_id, email_id, agent_id, ...).
        for key, value in record.__dict__.items():
            if key in _RESERVED_LOG_ATTRS:
                continue
            payload[key] = _redact(key, value)

        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)

        return json.dumps(payload, ensure_ascii=False, default=str)


def configure_logging(level: str = "INFO") -> None:
    """Configure the root logger to emit structured JSON to stdout."""
    handler = logging.StreamHandler(stream=sys.stdout)
    handler.setFormatter(JsonFormatter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level.upper())


def get_logger(name: str) -> logging.Logger:
    """Return a named logger."""
    return logging.getLogger(name)
