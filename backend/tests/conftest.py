"""Shared pytest fixtures."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from app.main import create_app
from fastapi.testclient import TestClient


@pytest.fixture
def client() -> Iterator[TestClient]:
    """A TestClient bound to a freshly created app instance."""
    app = create_app()
    with TestClient(app) as test_client:
        yield test_client
