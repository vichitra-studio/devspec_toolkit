"""Integration test for specdev llm bundle against the real host-repo spec dir.

Skipped unless SPECDEV_BUNDLE_INTEGRATION=1 is set.
Run from devspec_toolkit directory with:
    SPECDEV_BUNDLE_INTEGRATION=1 pytest tests/integration/test_bundle_integration.py -v
"""
from __future__ import annotations

import os

import pytest

from specdev_tools.llm.bundle import run_bundle


@pytest.mark.skipif(not os.environ.get("SPECDEV_BUNDLE_INTEGRATION"), reason="integration only")
def test_bundle_step_04_real_spec():
    result = run_bundle(step="04", spec_root="../spec", repo_root=".", git_root="..")
    assert result["ok"] is True
    assert result["bundle_version"] == "1"
    assert "step_structure_summary" in result


@pytest.mark.skipif(not os.environ.get("SPECDEV_BUNDLE_INTEGRATION"), reason="integration only")
def test_bundle_step_04_with_task_scoped_entries():
    result = run_bundle(step="04", spec_root="../spec", repo_root=".", git_root="..")
    # Without --task: scoped_entries must be empty
    assert result["scoped_entries"] == []
    # AC#8: < 50 KB target (design decision: path-pointers for large slots)
    import json
    size = len(json.dumps(result))
    assert size < 50 * 1024, f"Bundle too large: {size/1024:.1f} KB (limit 50 KB)"
