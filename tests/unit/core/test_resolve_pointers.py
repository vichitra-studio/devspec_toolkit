"""Unit tests for specdev_tools.core.json_utils resolve_pointers.

Tests cover:
- Happy path: id pointer that resolves, jq_path pointer that resolves
- Miss types: missing_file, missing_path (id not found), missing_path (jq_path null)
- Invalid shapes: forbidden per §4.3
- Nearest-id suggestions on id miss
- Malformed input JSON (stdin helper)
- Empty input list
- --out / stdout wiring
- File-parse error (corrupt JSON file)
- B1: path traversal containment
- B2: kind derivation via registry lookup for known files
- C1: temp path category enforcement
- C2: canonical_refs_used filtered from nearest[] corpus
- C4: {"pointers": [...]} envelope rejected
- Registry path: non-`id` primary keys resolve deterministically via entry_key_registry
"""
from __future__ import annotations

import json
import os
import tempfile
from io import StringIO
from typing import Any, Dict
from unittest.mock import patch

from specdev_tools.core.json_utils import (
    _is_valid_pointer_shape,
    _levenshtein,
    _nearest_ids,
    resolve_pointers,
    resolve_pointers_from_stdin,
)


# ---------------------------------------------------------------------------
# Fixture registry path (for T1 + T2 registered-filename tests)
# ---------------------------------------------------------------------------

_FIXTURE_DIR = os.path.normpath(os.path.join(
    os.path.dirname(__file__),
    "..", "..", "fixtures", "entry_key_registry",
))
"""Directory containing entry_key_registry.json for toolkit unit tests."""


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

SAMPLE_SPEC = {
    "$schema": "vc:04-fr-list",
    "id": "test-catalog",
    "functional_requirements": [
        {
            "fr_id": "fr-newsletter-subscribe",
            "name": "Newsletter Subscribe",
            "owner": "product",
        },
        {
            "fr_id": "fr-newsletter-confirm",
            "name": "Newsletter Confirm",
            "owner": "product",
        },
        {
            "fr_id": "fr-user-login",
            "name": "User Login",
            "owner": "api",
        },
    ],
}

# Spec with a "capabilities" array to test registry kind derivation.
# Uses capability_id to match the fixture registry for 01_capabilities.json.
CAPABILITIES_SPEC = {
    "$schema": "vc:01-capabilities",
    "capabilities": [
        {
            "capability_id": "cap-search",
            "name": "Search",
            "owner": "api",
        },
        {
            "capability_id": "cap-auth",
            "name": "Auth",
            "owner": "api",
        },
    ],
}

# Spec that uses inv_id as the primary entry key.
# Used to verify the registry resolves non-"id" primary keys deterministically.
INVARIANTS_SPEC = {
    "$schema": "vc:06-invariants",
    "rules": [
        {
            "inv_id": "inv-data-immutability",
            "name": "Data Immutability",
            "owner": "system",
        },
        {
            "inv_id": "inv-auth-required",
            "name": "Auth Required",
            "owner": "api",
        },
    ],
}

# Spec with canonical_refs_used to test C2 corpus filtering.
SPEC_WITH_CANONICAL_REFS = {
    "$schema": "vc:04-fr-list",
    "functional_requirements": [
        {
            "fr_id": "fr-real-one",
            "name": "Real FR",
            "owner": "product",
        }
    ],
    "canonical_refs_used": [
        {
            "id": "canon-ref-alpha",
            "name": "Some Canon Reference",
        },
        {
            "id": "canon-ref-beta",
            "name": "Another Canon Reference",
        },
    ],
}


class TmpSpecDir:
    """Context manager: creates a TemporaryDirectory and writes a JSON spec file
    into it as a relative path so that C1 temp-path checks do not trigger.

    Usage:
        with TmpSpecDir(SAMPLE_SPEC) as ctx:
            ptr = {"file": ctx.rel_name, "id": "fr-x"}
            report = resolve_pointers([ptr], git_root=ctx.dir, spec_root=_FIXTURE_DIR)
    """

    def __init__(self, data: Any, filename: str = "04_fr_list.json") -> None:
        self._data = data
        self._filename = filename
        self._tmpdir: tempfile.TemporaryDirectory | None = None

    def __enter__(self) -> "TmpSpecDir":
        self._tmpdir = tempfile.TemporaryDirectory()
        self.dir = self._tmpdir.name
        self.rel_name = self._filename
        self.abs_path = os.path.join(self.dir, self._filename)
        with open(self.abs_path, "w", encoding="utf-8") as fh:
            json.dump(self._data, fh, indent=2)
        return self

    def __exit__(self, *_: Any) -> None:
        if self._tmpdir:
            self._tmpdir.cleanup()


# Legacy helper kept for tests that use absolute paths explicitly (e.g. B1 tests).
def write_tmp_json(data: Any, directory: str) -> str:
    """Write data into directory as spec.json and return its relative name."""
    abs_path = os.path.join(directory, "spec.json")
    with open(abs_path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
    return "spec.json"


# ---------------------------------------------------------------------------
# Shape validation (§4.1 / §4.3)
# ---------------------------------------------------------------------------


class TestPointerShapeValidation:
    def test_valid_id_pointer(self) -> None:
        ok, reason = _is_valid_pointer_shape({"file": "spec/04_fr_list.json", "id": "fr-x"})
        assert ok
        assert reason == ""

    def test_valid_jq_path_pointer(self) -> None:
        ok, _ = _is_valid_pointer_shape(
            {"file": "spec/04_fr_list.json", "jq_path": ".functional_requirements[0]"}
        )
        assert ok

    def test_bare_string_is_invalid(self) -> None:
        ok, reason = _is_valid_pointer_shape("fr-x")
        assert not ok
        assert "invalid_shape" in reason

    def test_file_only_no_id_or_jq(self) -> None:
        ok, reason = _is_valid_pointer_shape({"file": "spec/04_fr_list.json"})
        assert not ok
        assert "invalid_shape" in reason

    def test_missing_file_field(self) -> None:
        ok, reason = _is_valid_pointer_shape({"id": "fr-x"})
        assert not ok
        assert "invalid_shape" in reason

    def test_forbidden_specdev_prefix(self) -> None:
        ok, reason = _is_valid_pointer_shape({"file": ".specdev/cache.json", "id": "fr-x"})
        assert not ok
        assert "invalid_shape" in reason

    def test_forbidden_txt_extension(self) -> None:
        ok, reason = _is_valid_pointer_shape({"file": "dump.txt", "id": "fr-x"})
        assert not ok
        assert "invalid_shape" in reason

    def test_none_is_invalid(self) -> None:
        ok, _ = _is_valid_pointer_shape(None)
        assert not ok

    # C1: absolute temp paths
    def test_forbidden_tmp_path(self) -> None:
        ok, reason = _is_valid_pointer_shape({"file": "/tmp/foo.json", "id": "fr-x"})
        assert not ok
        assert "invalid_shape" in reason

    def test_forbidden_var_folders_path(self) -> None:
        ok, reason = _is_valid_pointer_shape(
            {"file": "/var/folders/ab/cdef/T/something.json", "id": "fr-x"}
        )
        assert not ok
        assert "invalid_shape" in reason


# ---------------------------------------------------------------------------
# Levenshtein / nearest-id helpers
# ---------------------------------------------------------------------------


class TestLevenshtein:
    def test_identical_strings(self) -> None:
        assert _levenshtein("abc", "abc") == 0

    def test_empty_string(self) -> None:
        assert _levenshtein("abc", "") == 3
        assert _levenshtein("", "abc") == 3

    def test_single_substitution(self) -> None:
        assert _levenshtein("abc", "axc") == 1


class TestNearestIds:
    def test_returns_top_n(self) -> None:
        candidates = ["fr-newsletter-subscribe", "fr-newsletter-confirm", "fr-user-login", "fr-other"]
        results = _nearest_ids("fr-newslettr-subscribe", candidates, top_n=2)
        assert len(results) == 2
        # closest should be fr-newsletter-subscribe (typo)
        assert results[0]["id"] == "fr-newsletter-subscribe"

    def test_empty_candidates(self) -> None:
        assert _nearest_ids("fr-x", [], top_n=3) == []

    def test_scores_between_0_and_1(self) -> None:
        results = _nearest_ids("fr-x", ["fr-x", "fr-y"], top_n=3)
        for r in results:
            assert 0.0 <= r["score"] <= 1.0

    def test_exact_match_scores_1(self) -> None:
        results = _nearest_ids("fr-x", ["fr-x", "fr-y"], top_n=3)
        assert results[0]["score"] == 1.0
        assert results[0]["id"] == "fr-x"


# ---------------------------------------------------------------------------
# resolve_pointers — happy paths
# ---------------------------------------------------------------------------


class TestResolvePointersHappy:
    def test_id_pointer_resolves(self) -> None:
        with TmpSpecDir(SAMPLE_SPEC) as ctx:
            ptr = {"file": ctx.rel_name, "id": "fr-newsletter-subscribe"}
            report = resolve_pointers([ptr], git_root=ctx.dir, spec_root=_FIXTURE_DIR)
            r = report["results"][0]
            assert r["exists"] is True
            assert r["kind"] == "functional_requirement"
            assert ".functional_requirements[0]" in r["jq_path"]
            assert report["summary"]["hits"] == 1
            assert report["summary"]["misses"] == 0

    def test_jq_path_pointer_resolves(self) -> None:
        with TmpSpecDir(SAMPLE_SPEC) as ctx:
            ptr = {"file": ctx.rel_name, "jq_path": ".functional_requirements[1]"}
            report = resolve_pointers([ptr], git_root=ctx.dir, spec_root=_FIXTURE_DIR)
            r = report["results"][0]
            assert r["exists"] is True
            assert r["jq_path"] == ".functional_requirements[1]"
            assert "value_preview" in r

    def test_multiple_pointers_mixed(self) -> None:
        with TmpSpecDir(SAMPLE_SPEC) as ctx:
            ptrs = [
                {"file": ctx.rel_name, "id": "fr-user-login"},
                {"file": ctx.rel_name, "id": "fr-newsletter-subscribe"},
            ]
            report = resolve_pointers(ptrs, git_root=ctx.dir, spec_root=_FIXTURE_DIR)
            assert report["summary"]["hits"] == 2
            assert report["summary"]["misses"] == 0

    def test_value_preview_has_at_most_3_keys(self) -> None:
        with TmpSpecDir(SAMPLE_SPEC) as ctx:
            ptr = {"file": ctx.rel_name, "id": "fr-newsletter-subscribe"}
            report = resolve_pointers([ptr], git_root=ctx.dir, spec_root=_FIXTURE_DIR)
            preview = report["results"][0]["value_preview"]
            assert isinstance(preview, dict)
            assert len(preview) <= 3

    def test_git_root_relative_file(self) -> None:
        """Pointer uses path relative to git_root."""
        with TmpSpecDir(SAMPLE_SPEC) as ctx:
            ptr = {"file": ctx.rel_name, "id": "fr-user-login"}
            report = resolve_pointers([ptr], git_root=ctx.dir, spec_root=_FIXTURE_DIR)
            assert report["results"][0]["exists"] is True

    # B2: capabilities array → kind "capability" via registry
    def test_capabilities_kind_derivation(self) -> None:
        with TmpSpecDir(CAPABILITIES_SPEC, filename="01_capabilities.json") as ctx:
            ptr = {"file": ctx.rel_name, "id": "cap-search"}
            report = resolve_pointers([ptr], git_root=ctx.dir, spec_root=_FIXTURE_DIR)
            r = report["results"][0]
            assert r["exists"] is True
            assert r["kind"] == "capability", f"got kind={r['kind']!r}"

    # B2: jq_path branch also resolves kind via registry
    def test_capabilities_jq_path_kind_derivation(self) -> None:
        with TmpSpecDir(CAPABILITIES_SPEC, filename="01_capabilities.json") as ctx:
            ptr = {"file": ctx.rel_name, "jq_path": ".capabilities[0]"}
            report = resolve_pointers([ptr], git_root=ctx.dir, spec_root=_FIXTURE_DIR)
            r = report["results"][0]
            assert r["exists"] is True
            assert r["kind"] == "capability", f"got kind={r['kind']!r}"

    # §5.1: results must be ordered to match input pointer order
    def test_results_preserve_input_order(self) -> None:
        with TmpSpecDir(SAMPLE_SPEC) as ctx:
            ptrs = [
                {"file": ctx.rel_name, "id": "fr-bogus"},               # miss
                {"file": ctx.rel_name, "id": "fr-user-login"},          # hit
                {"file": ctx.rel_name, "id": "fr-newsletter-confirm"},  # hit
            ]
            report = resolve_pointers(ptrs, git_root=ctx.dir, spec_root=_FIXTURE_DIR)
            statuses = [r["exists"] for r in report["results"]]
            assert statuses == [False, True, True]
            # Pointer field round-trips in order
            for ptr_in, result in zip(ptrs, report["results"]):
                assert result["pointer"] == ptr_in

    # B1: path with normpath-collapsible traversal that stays inside git_root should resolve
    def test_traversal_that_stays_in_root_resolves(self) -> None:
        with TmpSpecDir(SAMPLE_SPEC) as ctx:
            # "subdir/../04_fr_list.json" normalises to "04_fr_list.json" — inside git_root
            ptr = {"file": f"subdir/../{ctx.rel_name}", "id": "fr-user-login"}
            report = resolve_pointers([ptr], git_root=ctx.dir, spec_root=_FIXTURE_DIR)
            # After normpath it's just 04_fr_list.json inside ctx.dir — should be a hit
            assert report["results"][0]["exists"] is True


# ---------------------------------------------------------------------------
# resolve_pointers — miss types
# ---------------------------------------------------------------------------


class TestResolvePointersMisses:
    def test_missing_file(self) -> None:
        ptr = {"file": "nonexistent_spec.json", "id": "fr-x"}
        with tempfile.TemporaryDirectory() as tmpdir:
            report = resolve_pointers([ptr], git_root=tmpdir, spec_root=_FIXTURE_DIR)
            r = report["results"][0]
            assert r["exists"] is False
            assert "missing_file" in r["reason"]
            assert report["summary"]["misses"] == 1

    def test_missing_id(self) -> None:
        with TmpSpecDir(SAMPLE_SPEC) as ctx:
            ptr = {"file": ctx.rel_name, "id": "fr-nonexistent"}
            report = resolve_pointers([ptr], git_root=ctx.dir, spec_root=_FIXTURE_DIR)
            r = report["results"][0]
            assert r["exists"] is False
            assert "nearest" in r
            assert len(r["nearest"]) > 0

    def test_missing_jq_path(self) -> None:
        with TmpSpecDir(SAMPLE_SPEC) as ctx:
            ptr = {"file": ctx.rel_name, "jq_path": ".functional_requirements[99]"}
            report = resolve_pointers([ptr], git_root=ctx.dir, spec_root=_FIXTURE_DIR)
            r = report["results"][0]
            assert r["exists"] is False
            assert "missing_path" in r["reason"]

    def test_invalid_shape_in_results(self) -> None:
        ptr = "bare-string"
        report = resolve_pointers([ptr], spec_root=_FIXTURE_DIR)
        r = report["results"][0]
        assert r["exists"] is False
        assert "invalid_shape" in r["reason"]

    def test_forbidden_path_in_results(self) -> None:
        ptr = {"file": ".specdev/cache.json", "id": "x"}
        report = resolve_pointers([ptr], spec_root=_FIXTURE_DIR)
        r = report["results"][0]
        assert r["exists"] is False
        assert "invalid_shape" in r["reason"]

    def test_nearest_ids_on_typo(self) -> None:
        """Typo 'fr-newslettr-subscribe' should surface real id as top nearest."""
        with TmpSpecDir(SAMPLE_SPEC) as ctx:
            ptr = {"file": ctx.rel_name, "id": "fr-newslettr-subscribe"}
            report = resolve_pointers([ptr], git_root=ctx.dir, spec_root=_FIXTURE_DIR)
            r = report["results"][0]
            assert r["exists"] is False
            top_nearest = r["nearest"][0]["id"]
            assert top_nearest == "fr-newsletter-subscribe"

    def test_file_parse_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            corrupt_path = os.path.join(tmpdir, "corrupt.json")
            with open(corrupt_path, "w") as fh:
                fh.write("{not valid json")
            ptr = {"file": "corrupt.json", "id": "fr-x"}
            report = resolve_pointers([ptr], git_root=tmpdir, spec_root=_FIXTURE_DIR)
            r = report["results"][0]
            assert r["exists"] is False
            assert "file_parse_error" in r["reason"]

    def test_directory_pointer(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            # Use a relative path that resolves to the tmpdir itself
            ptr = {"file": ".", "id": "fr-x"}
            report = resolve_pointers([ptr], git_root=tmpdir, spec_root=_FIXTURE_DIR)
            r = report["results"][0]
            assert r["exists"] is False
            assert "invalid_shape" in r["reason"]

    # B1: path traversal escaping git_root → miss with escape reason
    def test_path_traversal_escape_is_miss(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            ptr = {"file": "../etc/passwd", "id": "x"}
            report = resolve_pointers([ptr], git_root=tmpdir, spec_root=_FIXTURE_DIR)
            r = report["results"][0]
            assert r["exists"] is False
            assert "path_escapes_git_root" in r["reason"]

    # C1: absolute /tmp/ path → invalid_shape miss
    def test_tmp_path_is_invalid_shape_miss(self) -> None:
        ptr = {"file": "/tmp/foo.json", "id": "x"}
        report = resolve_pointers([ptr], spec_root=_FIXTURE_DIR)
        r = report["results"][0]
        assert r["exists"] is False
        assert "invalid_shape" in r["reason"]

    # C1: absolute /var/folders path → invalid_shape miss
    def test_var_folders_path_is_invalid_shape_miss(self) -> None:
        ptr = {"file": "/var/folders/ab/cdef/T/something.json", "id": "x"}
        report = resolve_pointers([ptr], spec_root=_FIXTURE_DIR)
        r = report["results"][0]
        assert r["exists"] is False
        assert "invalid_shape" in r["reason"]

    # C2: nearest[] must not contain entries from canonical_refs_used
    def test_nearest_excludes_canonical_refs_used(self) -> None:
        with TmpSpecDir(SPEC_WITH_CANONICAL_REFS) as ctx:
            # Look for a missing fr-* id — nearest should not surface canon-ref-* entries
            ptr = {"file": ctx.rel_name, "id": "fr-bogus-id"}
            report = resolve_pointers([ptr], git_root=ctx.dir, spec_root=_FIXTURE_DIR)
            r = report["results"][0]
            assert r["exists"] is False
            nearest_ids = [n["id"] for n in r.get("nearest", [])]
            assert not any("canon-ref" in nid for nid in nearest_ids), (
                f"canonical_refs_used entries leaked into nearest: {nearest_ids}"
            )


# ---------------------------------------------------------------------------
# Empty input
# ---------------------------------------------------------------------------


class TestResolvePointersEmpty:
    def test_empty_list(self) -> None:
        report = resolve_pointers([], spec_root=_FIXTURE_DIR)
        assert report["results"] == []
        assert report["summary"]["hits"] == 0
        assert report["summary"]["misses"] == 0


# ---------------------------------------------------------------------------
# resolve_pointers_from_stdin — stdin/stdout wiring
# ---------------------------------------------------------------------------


class TestResolvePointersFromStdin:
    def _run_stdin(self, payload: str, out_path: str | None = None, git_root: str | None = None) -> Dict[str, Any]:
        with patch("sys.stdin", StringIO(payload)):
            captured = StringIO()
            if out_path is None:
                with patch("sys.stdout", captured):
                    resolve_pointers_from_stdin(out_path=None, git_root=git_root, spec_root=_FIXTURE_DIR)
                return json.loads(captured.getvalue())
            else:
                resolve_pointers_from_stdin(out_path=out_path, git_root=git_root, spec_root=_FIXTURE_DIR)
                with open(out_path, encoding="utf-8") as fh:
                    return json.load(fh)

    def test_absolute_temp_path_via_stdin_is_rejected(self) -> None:
        """C1: an absolute /var/folders path sent via stdin is rejected as invalid_shape."""
        with TmpSpecDir(SAMPLE_SPEC) as ctx:
            payload = json.dumps([{"file": ctx.abs_path, "id": "fr-user-login"}])
            report = self._run_stdin(payload)
            # C1: absolute /var/folders path → invalid_shape miss
            assert report["summary"]["misses"] == 1
            assert "invalid_shape" in report["results"][0]["reason"]

    def test_valid_list_to_stdout_relative(self) -> None:
        with TmpSpecDir(SAMPLE_SPEC) as ctx:
            payload = json.dumps([{"file": ctx.rel_name, "id": "fr-user-login"}])
            with patch("sys.stdin", StringIO(payload)):
                captured = StringIO()
                with patch("sys.stdout", captured):
                    resolve_pointers_from_stdin(out_path=None, git_root=ctx.dir, spec_root=_FIXTURE_DIR)
                report = json.loads(captured.getvalue())
            assert report["summary"]["hits"] == 1

    def test_malformed_json_returns_parse_error(self) -> None:
        report = self._run_stdin("{not json}")
        assert "parse_error" in report
        assert report["summary"]["hits"] == 0

    def test_empty_stdin_returns_empty_report(self) -> None:
        report = self._run_stdin("")
        assert report["results"] == []

    # C4: {"pointers": [...]} envelope must now be rejected (not unwrapped)
    def test_wrapped_pointers_envelope_is_rejected(self) -> None:
        with TmpSpecDir(SAMPLE_SPEC) as ctx:
            payload = json.dumps(
                {"pointers": [{"file": ctx.rel_name, "id": "fr-newsletter-subscribe"}]}
            )
            with patch("sys.stdin", StringIO(payload)):
                captured = StringIO()
                with patch("sys.stdout", captured):
                    resolve_pointers_from_stdin(out_path=None, git_root=ctx.dir, spec_root=_FIXTURE_DIR)
                report = json.loads(captured.getvalue())
            # Must be a parse/shape error — NOT a hit
            assert "parse_error" in report
            assert report["summary"]["hits"] == 0

    def test_out_file_wiring(self) -> None:
        with TmpSpecDir(SAMPLE_SPEC) as ctx:
            payload = json.dumps([{"file": ctx.rel_name, "id": "fr-user-login"}])
            fd, out_path = tempfile.mkstemp(suffix=".json")
            os.close(fd)
            try:
                with patch("sys.stdin", StringIO(payload)):
                    resolve_pointers_from_stdin(out_path=out_path, git_root=ctx.dir, spec_root=_FIXTURE_DIR)
                with open(out_path, encoding="utf-8") as fh:
                    report = json.load(fh)
                assert report["summary"]["hits"] == 1
            finally:
                os.unlink(out_path)

    def test_always_exits_0_on_bad_input(self) -> None:
        """resolve_pointers_from_stdin must never raise; always exits cleanly."""
        with patch("sys.stdin", StringIO("{bad")):
            captured = StringIO()
            with patch("sys.stdout", captured):
                # Should not raise
                resolve_pointers_from_stdin(out_path=None, git_root=None, spec_root=_FIXTURE_DIR)
            report = json.loads(captured.getvalue())
            assert "parse_error" in report


# ---------------------------------------------------------------------------
# Registry-based deterministic non-"id" primary key resolution
# ---------------------------------------------------------------------------


class TestRegistryPrimaryKeyResolution:
    """Verify that entries using a non-bare-"id" primary key (e.g. inv_id)
    are found via the entry-key registry, so the result is deterministic
    even when an entry has multiple *_id fields.
    """

    def test_inv_id_primary_key_resolves(self) -> None:
        """inv_id is registered for 06_invariants.json rules[].
        The pointer must hit with kind='rule' and the correct jq_path.
        """
        with TmpSpecDir(INVARIANTS_SPEC, filename="06_invariants.json") as ctx:
            ptr = {"file": ctx.rel_name, "id": "inv-data-immutability"}
            report = resolve_pointers([ptr], git_root=ctx.dir, spec_root=_FIXTURE_DIR)
            r = report["results"][0]
            assert r["exists"] is True, f"expected hit; got: {r}"
            assert r["kind"] == "rule", f"expected kind='rule', got kind={r['kind']!r}"
            assert r["jq_path"] == ".rules[0]"

    def test_inv_id_second_entry_resolves(self) -> None:
        """Second entry in rules[] resolves to correct index deterministically."""
        with TmpSpecDir(INVARIANTS_SPEC, filename="06_invariants.json") as ctx:
            ptr = {"file": ctx.rel_name, "id": "inv-auth-required"}
            report = resolve_pointers([ptr], git_root=ctx.dir, spec_root=_FIXTURE_DIR)
            r = report["results"][0]
            assert r["exists"] is True, f"expected hit; got: {r}"
            assert r["jq_path"] == ".rules[1]"

    def test_inv_id_miss_surfaces_nearest(self) -> None:
        """A typo on an inv_id produces a miss with nearest[] containing real inv_ids."""
        with TmpSpecDir(INVARIANTS_SPEC, filename="06_invariants.json") as ctx:
            ptr = {"file": ctx.rel_name, "id": "inv-data-immutabilty"}  # typo
            report = resolve_pointers([ptr], git_root=ctx.dir, spec_root=_FIXTURE_DIR)
            r = report["results"][0]
            assert r["exists"] is False
            assert "nearest" in r and len(r["nearest"]) > 0
            assert r["nearest"][0]["id"] == "inv-data-immutability"


# ---------------------------------------------------------------------------
# T1 + T2: _resolve_single_pointer through registered-filename path
# ---------------------------------------------------------------------------

# SAMPLE_SPEC (defined above) is the FR spec — used as the fixture for T1.

SAMPLE_ROADMAP_SPEC = {
    "$schema": "vc:14-roadmap",
    "milestones": [
        {
            "milestone_id": "ms-1",
            "name": "Phase 1",
            "tasks": [
                {"task_id": "task-setup-env", "description": "Set up environment"},
                {"task_id": "task-build-theme", "description": "Build theme"},
            ],
            "deliverables": [],
        }
    ],
    "dependencies": [],
    "trace": [],
}


class TestResolveSinglePointerRegistryPath:
    """T1 + T2: exercise _resolve_single_pointer through a registered filename,
    exercising the registry-aware id-lookup path (not the fallback 'spec.json' path).
    """

    def test_T1_fr_list_registered_filename_hit(self) -> None:
        """T1: resolve a known fr_id via the registered 04_fr_list.json path."""
        with TmpSpecDir(SAMPLE_SPEC, filename="04_fr_list.json") as ctx:
            ptr = {"file": "04_fr_list.json", "id": "fr-newsletter-subscribe"}
            report = resolve_pointers([ptr], git_root=ctx.dir, spec_root=_FIXTURE_DIR)
            r = report["results"][0]
            assert r["exists"] is True, f"expected hit; got: {r}"
            assert r["kind"] == "functional_requirement"
            assert r["jq_path"] == ".functional_requirements[0]"
            assert report["summary"]["hits"] == 1

    def test_T2_roadmap_nested_task_registered_filename_hit(self) -> None:
        """T2: resolve a nested task_id via the registered 14_roadmap.json path."""
        with TmpSpecDir(SAMPLE_ROADMAP_SPEC, filename="14_roadmap.json") as ctx:
            ptr = {"file": "14_roadmap.json", "id": "task-build-theme"}
            report = resolve_pointers([ptr], git_root=ctx.dir, spec_root=_FIXTURE_DIR)
            r = report["results"][0]
            assert r["exists"] is True, f"expected hit; got: {r}"
            assert r["kind"] == "task"
            # task-build-theme is at milestones[0].tasks[1]
            assert r["jq_path"] == ".milestones[0].tasks[1]"
            assert report["summary"]["hits"] == 1


# ---------------------------------------------------------------------------
# CLI integration via specdev json resolve-pointers
# ---------------------------------------------------------------------------


class TestCLIResolvePointers:
    """Integration-level test: invoke the CLI entry point."""

    def test_cli_exits_0_on_hit(self) -> None:
        from specdev_tools.core.json_utils import main as json_main
        with TmpSpecDir(SAMPLE_SPEC) as ctx:
            payload = json.dumps([{"file": ctx.rel_name, "id": "fr-user-login"}])
            with patch("sys.stdin", StringIO(payload)):
                with patch("sys.argv", ["json", "resolve-pointers",
                                        "--git-root", ctx.dir,
                                        "--spec-root", _FIXTURE_DIR]):
                    captured = StringIO()
                    with patch("sys.stdout", captured):
                        json_main()  # must not raise or sys.exit(1)
            report = json.loads(captured.getvalue())
            assert report["summary"]["hits"] == 1

    def test_cli_exits_0_on_miss(self) -> None:
        from specdev_tools.core.json_utils import main as json_main
        with TmpSpecDir(SAMPLE_SPEC) as ctx:
            payload = json.dumps([{"file": ctx.rel_name, "id": "fr-bogus"}])
            with patch("sys.stdin", StringIO(payload)):
                with patch("sys.argv", ["json", "resolve-pointers",
                                        "--git-root", ctx.dir,
                                        "--spec-root", _FIXTURE_DIR]):
                    captured = StringIO()
                    with patch("sys.stdout", captured):
                        json_main()
            report = json.loads(captured.getvalue())
            assert report["summary"]["misses"] == 1

    def test_cli_exits_0_on_bad_json(self) -> None:
        from specdev_tools.core.json_utils import main as json_main
        with patch("sys.stdin", StringIO("{bad json")):
            with patch("sys.argv", ["json", "resolve-pointers",
                                    "--spec-root", _FIXTURE_DIR]):
                captured = StringIO()
                with patch("sys.stdout", captured):
                    json_main()
        report = json.loads(captured.getvalue())
        assert "parse_error" in report
