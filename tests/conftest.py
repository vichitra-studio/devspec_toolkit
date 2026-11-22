"""Shared test fixtures for DevSpec Toolkit test suite."""
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIR = REPO_ROOT / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))


@pytest.fixture(scope="session")
def toolkit_1_2_0() -> Path:
    """The toolkit root a migration test runs against: this checkout, which says 1.2.0 (real schemas, canon, registries and changelog).

    A test that needs a root with other content (another version, an empty changelog) builds the fake one:
    ``unit.migration._support.make_toolkit``.
    """
    return REPO_ROOT


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


@pytest.fixture(autouse=True)
def _clear_shared_schema_caches():
    """Clear the shared SchemaRegistry / validator caches before each test.

    The caches (specdev_tools.core.registry) memoise registries and validators
    per repo_root; tests that monkeypatch validator constructors or rewrite
    schemas in a tmp toolkit must not see another test's cached objects.
    """
    from specdev_tools.core.registry import clear_shared_caches
    clear_shared_caches()
    yield


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


@pytest.fixture
def registered_checks():
    """Lets a test register ``spec-check`` checks: each check it registered is removed again when the test ends."""
    from specdev_tools.validation.check_registry import CHECK_REGISTRY, unregister_check

    before = {spec.name for spec in CHECK_REGISTRY}
    yield
    for spec in list(CHECK_REGISTRY):
        if spec.name not in before:
            unregister_check(spec.name)
