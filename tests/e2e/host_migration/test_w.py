"""The migration of the real host W (opt-in): skipped unless ``SPECDEV_HOST_W`` names a copy of it (see ``conftest.py``).

``SPECDEV_HOST_STAGE=end`` runs the end-state test instead of the mechanical one: the copy is then the host after the
judgement pass, which the harness does not simulate.
"""

import os

import pytest

pytestmark = pytest.mark.host_migration

STAGE = os.environ.get("SPECDEV_HOST_STAGE", "mechanical")


@pytest.mark.skipif(STAGE != "mechanical", reason="SPECDEV_HOST_STAGE selects the end-state test")
def test_mechanical_stage(run_host):
    report = run_host("w", "mechanical")
    assert report.ok, report.render()


@pytest.mark.skipif(STAGE != "end", reason="set SPECDEV_HOST_STAGE=end on the migrated copy after the judgement pass")
def test_end_state(run_host):
    report = run_host("w", "end")
    assert report.ok, report.render()
