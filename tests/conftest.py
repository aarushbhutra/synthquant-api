"""
Pytest configuration and fixtures for SynthQuant API tests.
"""

import os
import pytest
from fastapi.testclient import TestClient

# Set environment variables before importing app modules
# This allows tests to use env vars for secrets
os.environ.setdefault("ADMIN_SECRET", "test_admin_secret_for_ci")
os.environ.setdefault("INITIAL_API_KEY", "sk-synthquant-test-001")

from app.main import app
from app.store import store
from app.config import VALID_API_KEYS, ADMIN_SECRET
from app.services.market_profiler import market_profiler


@pytest.fixture(scope="function")
def reset_store():
    """
    Reset the in-memory store and market profiler cache before each test.
    Ensures test isolation - state does not leak between tests.
    """
    store.clear_all()
    market_profiler.clear_cache()
    yield store
    # Cleanup after test (optional, but good practice)
    store.clear_all()
    market_profiler.clear_cache()


@pytest.fixture(scope="function")
def client(reset_store) -> TestClient:
    """
    Provide a TestClient instance with a fresh store.
    The reset_store fixture ensures isolation.
    """
    return TestClient(app)


@pytest.fixture
def valid_api_key() -> str:
    """Return a valid API key from the config."""
    # Use environment variable if set, otherwise use config
    env_key = os.environ.get("INITIAL_API_KEY")
    if env_key and env_key in VALID_API_KEYS:
        return env_key
    return next(iter(VALID_API_KEYS))


@pytest.fixture
def invalid_api_key() -> str:
    """Return an invalid API key for testing."""
    return "sk-invalid-key-12345"


@pytest.fixture
def admin_secret() -> str:
    """Return the admin secret for testing hidden endpoints."""
    return ADMIN_SECRET


@pytest.fixture
def wrong_admin_secret() -> str:
    """Return an incorrect admin secret for testing."""
    return "wrong_secret_value"
