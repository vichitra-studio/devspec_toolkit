"""Unit tests for step_16a validator — review→plan feedback loop (W584).

Post-split, the 16a plan, 16b execution, and 16c review all live in the same
``spec/impl_context/{milestone_id}.json`` artifact that grows as phases run.
When chain-up validation reaches ``validate_step_16a`` for a 16c-phase
artifact, the ``review`` block is already on ``data`` — no sibling file lookup
required.  These tests inline ``review`` into the same data dict.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from specdev_tools.validation.validators.step_16 import _find_seed_manifest
from specdev_tools.validation.validators.step_16a import validate_step_16a


def _make_minimal_16a() -> dict:
    return {
        "$schema": "vc:16-impl-context",
        "id": "step-16a-test",
        "owner": "api",
        "created_at": "2024-01-01T00:00:00Z",
        "plan": {
            "status": "active",
            "summary": {
                "functional_summary": "Test implementation",
                "scope_in": ["auth-api"],
                "scope_out": [],
                "target_file_patterns": ["src/auth.py"],
            },
            "spec_alignment": {
                "requirements_summary": [{"theme": "Auth", "summary": "Login flow"}],
                "checklist": [],
            },
        },
    }


def _review_with_remediation(
    task_ids: list[str],
    linked_checklist_ids: dict[str, list[str]] | None = None,
) -> dict:
    linked = linked_checklist_ids or {}
    findings = []
    for task_id in task_ids:
        findings.append({
            "severity": "major",
            "description": f"Issue requiring {task_id}",
            "remediation_task": {
                "task_id": task_id,
                "summary": f"Fix for {task_id}",
                "files_to_touch": [],
                "checklist_ids": linked.get(task_id, [task_id]),
            },
        })
    return {"verdict": "needs_work", "findings": findings}


class TestStep16aFeedbackLoop(unittest.TestCase):
    """W584 fires when the review on this artifact surfaces a remediation_task
    that is not represented as a checklist item."""

    def test_no_review_no_w584(self):
        """A plan-only artifact (no review yet) never triggers W584."""
        data = _make_minimal_16a()
        errors = validate_step_16a(data, ".", spec_path=None)
        codes = [e.code for e in errors]
        self.assertNotIn("W584", codes)

    def test_review_with_all_tasks_covered_no_w584(self):
        """When remediation tasks are represented in the checklist, W584 stays quiet."""
        data = _make_minimal_16a()
        data["plan"]["spec_alignment"]["checklist"] = [
            {"id": "task-fix-auth", "spec_ref": {"type": "fr", "id": "fr-auth"}, "description": "Fix auth"},
        ]
        data["review"] = _review_with_remediation(["task-fix-auth"])
        errors = validate_step_16a(data, ".", spec_path=None)
        codes = [e.code for e in errors]
        self.assertNotIn("W584", codes)

    def test_review_with_uncovered_task_fires_w584(self):
        """A remediation_task missing from the checklist fires W584 with the task id in the message."""
        data = _make_minimal_16a()
        # Checklist is empty — remediation task is uncovered
        data["review"] = _review_with_remediation(["task-fix-missing"])
        errors = validate_step_16a(data, ".", spec_path=None)
        w584 = [e for e in errors if e.code == "W584"]
        self.assertEqual(len(w584), 1)
        self.assertIn("task-fix-missing", w584[0].message)

    def test_multiple_uncovered_tasks_fire_multiple_w584(self):
        """Each uncovered remediation task produces its own W584."""
        data = _make_minimal_16a()
        data["review"] = _review_with_remediation(["task-a", "task-b"])
        errors = validate_step_16a(data, ".", spec_path=None)
        w584_messages = {e.message for e in errors if e.code == "W584"}
        self.assertEqual(len(w584_messages), 2)

    def test_w584_silent_when_checklist_ids_all_valid(self):
        """W584 stays quiet when every remediation.checklist_ids entry resolves."""
        data = _make_minimal_16a()
        data["plan"]["spec_alignment"]["checklist"] = [
            {"id": "cl-real", "spec_ref": {"type": "fr", "id": "fr-real"}, "description": "Real work"},
        ]
        data["review"] = _review_with_remediation(
            ["task-xyz"],
            linked_checklist_ids={"task-xyz": ["cl-real"]},
        )
        errors = validate_step_16a(data, ".", spec_path=None)
        codes = [e.code for e in errors]
        self.assertNotIn("W584", codes)

    def test_review_feedback_does_not_require_spec_path(self):
        """W584 depends only on ``data`` — passing or omitting spec_path is equivalent."""
        data = _make_minimal_16a()
        data["review"] = _review_with_remediation(["task-only-in-review"])
        errors_no_path = validate_step_16a(data, ".", spec_path=None)
        errors_with_path = validate_step_16a(data, ".", spec_path="/tmp/any/path.json")
        codes_no_path = {e.code for e in errors_no_path}
        codes_with_path = {e.code for e in errors_with_path}
        self.assertIn("W584", codes_no_path)
        self.assertIn("W584", codes_with_path)


class TestFindSeedManifest(unittest.TestCase):
    """Unit tests for _find_seed_manifest host-discovery.

    Exercises the deterministic resolution strategy: spec_root-preferred when
    supplied, spec_path-relative fallback when not.  The unbounded upward walk
    has been removed (DEVSPEC-43); ancestor-escape is no longer possible.
    """

    def _write_manifest(self, base: Path) -> Path:
        """Write a minimal seed_manifest.json at base/spec/common/ and return its path."""
        manifest_dir = base / "spec" / "common"
        manifest_dir.mkdir(parents=True, exist_ok=True)
        manifest_path = manifest_dir / "seed_manifest.json"
        manifest_path.write_text(json.dumps({"doc_paths": ["docs/**/*.md"]}), encoding="utf-8")
        return manifest_path

    def test_anchor_artifact_finds_sibling_manifest(self):
        """Anchor at spec/16_impl_context.json resolves spec/common/seed_manifest.json."""
        with tempfile.TemporaryDirectory() as td:
            host = Path(td)
            expected = self._write_manifest(host)
            spec_path = str(host / "spec" / "16_impl_context.json")
            result = _find_seed_manifest(spec_path)
            self.assertEqual(result, str(expected))

    def test_milestone_plan_finds_host_manifest(self):
        """16a/16b/16c plan at spec/impl_context/ms_foo_plan.json resolves via parent.parent."""
        with tempfile.TemporaryDirectory() as td:
            host = Path(td)
            expected = self._write_manifest(host)
            impl_dir = host / "spec" / "impl_context"
            impl_dir.mkdir(parents=True)
            spec_path = str(impl_dir / "ms_auth_plan.json")
            result = _find_seed_manifest(spec_path)
            self.assertEqual(result, str(expected))

    def test_nested_host_path_finds_correct_manifest(self):
        """Works when spec is nested several levels deep (e.g. tmp/src/project/spec)."""
        with tempfile.TemporaryDirectory() as td:
            host = Path(td) / "src" / "project"
            expected = self._write_manifest(host)
            spec_path = str(host / "spec" / "16_impl_context.json")
            result = _find_seed_manifest(spec_path)
            self.assertEqual(result, str(expected))

    def test_no_manifest_returns_none(self):
        """Returns None when no seed_manifest.json exists at the deterministic location."""
        with tempfile.TemporaryDirectory() as td:
            spec_dir = Path(td) / "spec"
            spec_dir.mkdir()
            spec_path = str(spec_dir / "16_impl_context.json")
            result = _find_seed_manifest(spec_path)
            self.assertIsNone(result)

    def test_none_spec_path_returns_none(self):
        """Returns None gracefully when spec_path is None."""
        result = _find_seed_manifest(None)
        self.assertIsNone(result)

    def test_monorepo_ancestor_manifest_not_found_without_local_manifest(self):
        """DEVSPEC-43 fix: ancestor manifest is NOT returned when host has no local manifest.

        Previously the unbounded upward walk would escape the host boundary and return
        an ancestor workspace manifest.  With deterministic spec_path-relative resolution,
        a host that lacks a local spec/common/seed_manifest.json correctly gets None
        (→ W570) rather than silently inheriting an ancestor's manifest.
        """
        with tempfile.TemporaryDirectory() as td:
            # Workspace root has a manifest — should NOT be picked up
            workspace = Path(td)
            self._write_manifest(workspace)

            # Host project lives under packages/project — no local manifest
            host_spec = workspace / "packages" / "project" / "spec"
            host_spec.mkdir(parents=True)
            spec_path = str(host_spec / "16_impl_context.json")

            result = _find_seed_manifest(spec_path)
            # Ancestor-escape is prevented: no local manifest → None (not the workspace manifest)
            self.assertIsNone(result)

    # ── spec_root-preferred resolution (DEVSPEC-43) ───────────────────────────

    def test_spec_root_with_manifest_returns_it(self):
        """When spec_root is supplied and contains common/seed_manifest.json, return it."""
        with tempfile.TemporaryDirectory() as td:
            spec_root = Path(td) / "spec"
            expected = self._write_manifest(Path(td))
            result = _find_seed_manifest(spec_path=None, spec_root=str(spec_root))
            self.assertEqual(result, str(expected))

    def test_spec_root_without_manifest_returns_none(self):
        """When spec_root is supplied but has no manifest, return None (no fallback to walk)."""
        with tempfile.TemporaryDirectory() as td:
            # Create a spec_root dir — but NO manifest inside it
            spec_root = Path(td) / "spec"
            spec_root.mkdir(parents=True)
            # Put a manifest somewhere in the parent tree — must NOT be found
            ancestor = Path(td).parent
            (ancestor / "spec" / "common").mkdir(parents=True, exist_ok=True)
            (ancestor / "spec" / "common" / "seed_manifest.json").write_text(
                json.dumps({"doc_paths": []}), encoding="utf-8"
            )
            result = _find_seed_manifest(spec_path=None, spec_root=str(spec_root))
            self.assertIsNone(result)

    def test_declared_spec_root_suppresses_spec_path_fallback(self):
        """A declared spec_root with no manifest wins over a resolvable spec_path manifest.

        Discriminating assertion: if the code fell back to spec_path-relative resolution
        when spec_root has no manifest, _find_seed_manifest would return the spec_path
        manifest instead of None — so assertIsNone would fail, catching the regression.
        """
        with tempfile.TemporaryDirectory() as td:
            host = Path(td)

            # Set up a valid spec_path whose directory DOES contain common/seed_manifest.json
            spec_dir = host / "spec"
            spec_common = spec_dir / "common"
            spec_common.mkdir(parents=True)
            resolvable_manifest = spec_common / "seed_manifest.json"
            resolvable_manifest.write_text(
                json.dumps({"doc_paths": ["docs/**/*.md"]}), encoding="utf-8"
            )
            spec_path = str(spec_dir / "16_impl_context.json")

            # Sanity-check: spec_path alone WOULD resolve a manifest (proves it's a real target)
            self.assertIsNotNone(_find_seed_manifest(spec_path=spec_path, spec_root=None))

            # Set up a DIFFERENT spec_root that has NO manifest
            empty_spec_root = host / "alt_spec"
            empty_spec_root.mkdir(parents=True)

            # With spec_root declared (but empty), result must be None — NOT the spec_path manifest
            result = _find_seed_manifest(
                spec_path=spec_path, spec_root=str(empty_spec_root)
            )
            self.assertIsNone(
                result,
                "spec_root was declared but has no manifest; must return None without "
                "falling back to the spec_path-resolvable manifest",
            )

    def test_spec_root_takes_precedence_over_spec_path(self):
        """When spec_root is supplied, it is used regardless of what spec_path resolves to."""
        with tempfile.TemporaryDirectory() as td:
            host = Path(td)
            # spec_path-relative location has a manifest (should be ignored)
            self._write_manifest(host)
            # spec_root points to a different dir that also has a manifest
            alt_root = host / "alt_spec"
            alt_manifest = self._write_manifest(alt_root)

            spec_path = str(host / "spec" / "16_impl_context.json")
            result = _find_seed_manifest(spec_path=spec_path, spec_root=str(alt_root / "spec"))
            self.assertEqual(result, str(alt_manifest))


if __name__ == "__main__":
    unittest.main()
