"""Shared test fixtures for DevSpec Toolkit test suite."""
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIR = REPO_ROOT / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))


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
