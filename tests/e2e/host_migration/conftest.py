"""Collection rules and shared fixtures of the host-migration tests.

``test_w.py`` and ``test_p.py`` run on a COPY of a real host that the operator names in ``SPECDEV_HOST_W`` /
``SPECDEV_HOST_P`` (a git work tree whose ``spec/`` is committed; the stage writes into it, so it must be a throw-away
copy).  Without the variable every test of the file is skipped here, so collection never errors and CI (which has no hosts)
stays green.  Both files carry the ``host_migration`` marker (registered in ``tools/pyproject.toml``), so ``-m host_migration``
selects them and ``-m "not host_migration"`` leaves them out.

The other variables, all optional:

* ``SPECDEV_HOST_TOOLKIT``: a toolkit root that says 1.2.0 (default: this checkout itself; no copy is made);
* ``SPECDEV_HOST_STAGE``: ``mechanical`` (default) or ``end`` (the copy is the migrated host after the judgement pass);
* ``SPECDEV_HOST_EXPECT_W`` / ``SPECDEV_HOST_EXPECT_P``: a JSON file of counts the run must reproduce (kept OUTSIDE the repository);
* ``SPECDEV_HOST_BASE_REF``: the merge base of the end stage.
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from pathlib import Path

import pytest

from .harness import Report, check_end_state, compare_expect, run_mechanical_stage

HOST_VARIABLES = {"test_w.py": "SPECDEV_HOST_W", "test_p.py": "SPECDEV_HOST_P"}


def pytest_configure(config: pytest.Config) -> None:
    """Register the marker here too: ``tools/pyproject.toml`` is read only when pytest runs from ``tools/``, not from the repository root."""
    config.addinivalue_line("markers", "host_migration: runs the migration on a copy of a real host named by SPECDEV_HOST_W / SPECDEV_HOST_P (opt-in, skipped without them)")


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    for item in items:
        variable = HOST_VARIABLES.get(Path(str(item.fspath)).name)
        if variable is None:
            continue
        item.add_marker(pytest.mark.host_migration)
        named = os.environ.get(variable)
        if not named or not Path(named).is_dir():
            item.add_marker(pytest.mark.skip(reason=f"{variable} does not name a host copy"))


@pytest.fixture
def run_host(toolkit_1_2_0: Path) -> Callable[[str, str], Report]:
    """``run_host("w" | "p", "mechanical" | "end") -> Report`` on the copy named by the environment."""

    def run(kind: str, stage: str) -> Report:
        copy = Path(os.environ[HOST_VARIABLES[f"test_{kind}.py"]])
        toolkit = Path(os.environ.get("SPECDEV_HOST_TOOLKIT") or toolkit_1_2_0)
        if stage == "mechanical":
            report = run_mechanical_stage(copy, toolkit, kind)
        else:
            report = check_end_state(copy, toolkit, kind, base_ref=os.environ.get("SPECDEV_HOST_BASE_REF"))
        named = os.environ.get(f"SPECDEV_HOST_EXPECT_{kind.upper()}")
        if named:
            compare_expect(report, json.loads(Path(named).read_text(encoding="utf-8")))
        print(report.render())
        return report

    return run
