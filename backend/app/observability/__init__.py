"""Observability: structured logging and request context.

Centralizes structured (JSON) logging with automatic secret redaction so no
component leaks credentials into logs (RNF-04, ADR-002 security).
"""

from app.observability.logging import configure_logging, get_logger

__all__ = ["configure_logging", "get_logger"]
