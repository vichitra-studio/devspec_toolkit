"""Shared test helpers for invariant linter tests.

Centralised here so _make_spec_file is not duplicated across test modules.
"""
from __future__ import annotations

import json


def make_spec_file(tmp_path, rules, filename="06_invariants.json"):
    """Write a minimal step-06 invariant spec file into *tmp_path*."""
    spec = {
        "$schema": "vc:06-invariants",
        "id": "invariants-test",
        "owner": "api",
        "created_at": "2025-01-01T00:00:00Z",
        "rules": rules,
        "canonical_refs_used": [],
        "canonical_proposals": [],
        "canonical_conflicts": [],
    }
    path = tmp_path / filename
    path.write_text(json.dumps(spec), encoding="utf-8")
    return path
