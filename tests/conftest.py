"""Shared test fixtures for DevSpec Toolkit test suite."""
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIR = REPO_ROOT / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))


@pytest.fixture(autouse=True)
def _reset_specdev_config_singleton():
    """Reset the global SpecdevConfig singleton around every test.

    The singleton (specdev_tools.core.config._instance) is process-global; tests
    that mutate SPECDEV_* env vars and build it via get_config()/validate_dir can
    otherwise leak a stale config into unrelated tests (order-dependent flakes
    under pytest-randomly). Resetting before and after each test guarantees
    isolation.
    """
    from specdev_tools.core.config import reset_config
    reset_config()
    yield
    reset_config()


@pytest.fixture(scope="session")
def repo_root():
    """Return the toolkit repository root directory."""
    return REPO_ROOT


@pytest.fixture(scope="session")
def schema_root(repo_root):
    """Return the schema directory path."""
    return repo_root / "schema"


@pytest.fixture(scope="session")
def spec_root(repo_root):
    """Return the spec directory path."""
    return repo_root / "spec"


@pytest.fixture(scope="session")
def canon_root(repo_root):
    """Return the canonical registry directory path."""
    return repo_root / "canon"


@pytest.fixture(scope="session")
def fixtures_root(repo_root):
    """Return the test fixtures directory path."""
    return repo_root / "tests" / "fixtures"
