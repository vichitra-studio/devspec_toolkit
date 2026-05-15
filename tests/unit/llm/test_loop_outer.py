"""Unit tests for specdev_tools.llm.loop_outer — run_outer_loop.

All tests use tmp_path fixtures. Real snapshot/restore is exercised against
tmp_path spec dirs. run_spec_check_json is mocked to avoid needing a real
toolkit setup. json_patch is mocked where we test rollback without actual
file mutations.
"""
from __future__ import annotations

import json
import pathlib
from collections import deque
from typing import Any
from unittest.mock import patch

import pytest

from specdev_tools.llm.loop_outer import (
    _extract_step_id,
    _needs_forward_replay,
    run_outer_loop,
)
from specdev_tools.core.config import reset_config
from specdev_tools.context.snapshot import restore_snapshot, save_snapshot



# ---------------------------------------------------------------------------
# MockAdapter
# ---------------------------------------------------------------------------

class MockAdapter:
    """Queue-based mock LLMAdapter."""

    def __init__(self, responses: list[str]) -> None:
        self._queue: deque[str] = deque(responses)
        self.call_count = 0
        self.calls: list[tuple[str, str]] = []

    def chat(self, system: str, user: str) -> str:
        assert self._queue, (
            f"MockAdapter called too many times (already exhausted after "
            f"{self.call_count} call(s))"
        )
        self.call_count += 1
        self.calls.append((system, user))
        return self._queue.popleft()


# ---------------------------------------------------------------------------
# Synthetic spec environment
# ---------------------------------------------------------------------------

_FR_SPEC = {
    "$schema": "vc:04-fr-list",
    "id": "fr-list",
    "owner": "product",
    "functional_requirements": [
        {"fr_id": "fr-example-001", "owner": "api", "name": "First requirement"},
        {"fr_id": "fr-example-002", "owner": "api", "name": "Second requirement"},
    ],
}


def make_spec_dir(tmp_path: pathlib.Path) -> tuple[str, str, str]:
    """Build a minimal synthetic spec dir.

    Returns (spec_dir_str, git_root_str, repo_root_str).

    Layout:
        <tmp>/host/                         ← git_root
        <tmp>/host/spec/                    ← spec_dir
        <tmp>/host/spec/04_fr_list.json
        <tmp>/toolkit/                      ← repo_root
        <tmp>/toolkit/tools/step_order.json
    """
    git_root = tmp_path / "host"
    git_root.mkdir(parents=True)
    spec_dir = git_root / "spec"
    spec_dir.mkdir()
    (spec_dir / "04_fr_list.json").write_text(
        json.dumps(_FR_SPEC, indent=2), encoding="utf-8"
    )

    repo_root = tmp_path / "toolkit"
    (repo_root / "tools").mkdir(parents=True)
    step_order = {
        "steps": ["00", "01", "02", "03", "04", "05", "16c"],
    }
    (repo_root / "tools" / "step_order.json").write_text(
        json.dumps(step_order), encoding="utf-8"
    )

    return str(spec_dir), str(git_root), str(repo_root)


_TASK = "Update owner of fr-example-001 to product"
_STEP_SUMMARY: dict[str, Any] = {
    "spec/04_fr_list.json": {
        "entry_count": 2,
        "ids": ["fr-example-001", "fr-example-002"],
    }
}
_VALIDATED_POINTERS = [
    {"file": "spec/04_fr_list.json", "id": "fr-example-001"},
]


def _edit_response(file: str = "spec/04_fr_list.json") -> str:
    return json.dumps({
        "edits": [
            {"file": file, "jq_path": ".functional_requirements[0].owner", "value": "product"}
        ],
        "rationale": "Aligns owner with task requirement.",
    })


def _clean_ctx() -> dict[str, Any]:
    return {"checks": {"schema": {"status": "PASS", "error_count": 0, "warning_count": 0, "findings": []}}}


def _failing_ctx(findings: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    f = findings or [{"code": "E100", "message": "some error", "file": "spec/04_fr_list.json"}]
    return {"checks": {"schema": {"status": "FAIL", "error_count": len(f), "warning_count": 0, "findings": f}}}


# ---------------------------------------------------------------------------
# Helper: patch run_spec_check_json in loop_outer module
# ---------------------------------------------------------------------------

SPEC_CHECK_PATH = "specdev_tools.llm.loop_outer.run_spec_check_json"


# ---------------------------------------------------------------------------
# Unit tests: helper functions
# ---------------------------------------------------------------------------

class TestExtractStepId:
    def test_numeric(self) -> None:
        assert _extract_step_id("spec/04_fr_list.json") == "04"

    def test_alphanumeric(self) -> None:
        assert _extract_step_id("spec/02a_delivery_baseline.json") == "02a"

    def test_no_match(self) -> None:
        assert _extract_step_id("canon/manifest.json") is None

    def test_basename_only(self) -> None:
        assert _extract_step_id("04_fr_list.json") == "04"


class TestNeedsForwardReplay:
    def test_non_final_step_triggers_replay(self, tmp_path: pathlib.Path) -> None:
        _, _, repo_root = make_spec_dir(tmp_path)
        # step_order has 16c as last; 04 is not last → should trigger replay
        edits = [{"file": "spec/04_fr_list.json", "jq_path": ".x", "value": 1}]
        # Reset the module-level cache so it reads from this tmp repo_root
        import specdev_tools.llm.loop_outer as lo
        lo._STEP_ORDER_CACHE = {}
        assert _needs_forward_replay(edits, repo_root) is True

    def test_final_step_no_replay(self, tmp_path: pathlib.Path) -> None:
        _, _, repo_root = make_spec_dir(tmp_path)
        import specdev_tools.llm.loop_outer as lo
        lo._STEP_ORDER_CACHE = {}
        edits = [{"file": "spec/16c_something.json", "jq_path": ".x", "value": 1}]
        assert _needs_forward_replay(edits, repo_root) is False

    def test_non_spec_file_no_replay(self, tmp_path: pathlib.Path) -> None:
        _, _, repo_root = make_spec_dir(tmp_path)
        import specdev_tools.llm.loop_outer as lo
        lo._STEP_ORDER_CACHE = {}
        edits = [{"file": "canon/manifest.json", "jq_path": ".x", "value": 1}]
        assert _needs_forward_replay(edits, repo_root) is False


# ---------------------------------------------------------------------------
# Main test class
# ---------------------------------------------------------------------------

class TestRunOuterLoop:

    def setup_method(self) -> None:
        """Reset module caches between tests."""
        reset_config()
        import specdev_tools.llm.loop_outer as lo
        lo._STEP_ORDER_CACHE = {}
        lo._SCHEMA_CACHE = None
        lo._TEMPLATE_CACHE.clear()

    # -----------------------------------------------------------------------
    # 1. max_iters=0 guard
    # -----------------------------------------------------------------------

    def test_max_iters_zero_returns_immediately(self, tmp_path: pathlib.Path) -> None:
        """max_iters=0 → no LLM calls, no snapshot, ok=False with explicit reason."""
        spec_dir, git_root, repo_root = make_spec_dir(tmp_path)
        adapter = MockAdapter([])  # no responses queued

        result = run_outer_loop(
            task=_TASK,
            validated_pointers=_VALIDATED_POINTERS,
            step_structure_summary=_STEP_SUMMARY,
            adapter=adapter,
            repo_root=repo_root,
            spec_dir=spec_dir,
            git_root=git_root,
            max_iters=0,
        )

        assert result["ok"] is False
        assert result["applied"] is False
        assert result["iterations"] == 0
        assert result["files_changed"] == []
        assert result["snapshot_id"] == ""
        assert result["partial"] is True
        assert any("max_iters=0" in u.get("reason", "") for u in result["unresolved"])
        assert adapter.call_count == 0
        assert "spec_check" in result
        assert result["spec_check"]["forward_replay"] == []

    # -----------------------------------------------------------------------
    # 2. Happy path: clean on iter 1
    # -----------------------------------------------------------------------

    def test_happy_path_clean_first_iter(self, tmp_path: pathlib.Path) -> None:
        """Edits applied, spec-check clean on iter 1 → ok=True, applied=True."""
        spec_dir, git_root, repo_root = make_spec_dir(tmp_path)
        adapter = MockAdapter([_edit_response()])

        with patch(SPEC_CHECK_PATH, return_value=([], _clean_ctx())) as mock_sc, \
             patch("specdev_tools.llm.loop_outer.json_patch") as mock_patch:

            result = run_outer_loop(
                task=_TASK,
                validated_pointers=_VALIDATED_POINTERS,
                step_structure_summary=_STEP_SUMMARY,
                adapter=adapter,
                repo_root=repo_root,
                spec_dir=spec_dir,
                git_root=git_root,
                max_iters=5,
            )

        assert result["ok"] is True
        assert result["applied"] is True
        assert result["partial"] is False
        assert result["iterations"] == 1
        assert result["unresolved"] == []
        assert result["spec_check_status"] == "PASS"
        assert mock_sc.call_count == 1
        assert mock_patch.call_count == 1

    # -----------------------------------------------------------------------
    # 3. Repair path: iter 1 has findings, iter 2 clean
    # -----------------------------------------------------------------------

    def test_repair_path_clean_on_second_iter(self, tmp_path: pathlib.Path) -> None:
        """Iter 1 has spec-check findings; iter 2 is clean → ok=True."""
        spec_dir, git_root, repo_root = make_spec_dir(tmp_path)
        adapter = MockAdapter([_edit_response(), _edit_response()])

        spec_check_results = [
            ([], _failing_ctx()),  # iter 1: fail
            ([], _clean_ctx()),    # iter 2: pass
        ]

        with patch(SPEC_CHECK_PATH, side_effect=spec_check_results), \
             patch("specdev_tools.llm.loop_outer.json_patch"):

            result = run_outer_loop(
                task=_TASK,
                validated_pointers=_VALIDATED_POINTERS,
                step_structure_summary=_STEP_SUMMARY,
                adapter=adapter,
                repo_root=repo_root,
                spec_dir=spec_dir,
                git_root=git_root,
                max_iters=5,
            )

        assert result["ok"] is True
        assert result["applied"] is True
        assert result["iterations"] == 2

    # -----------------------------------------------------------------------
    # 4. Stagnation: error count doesn't shrink for 2 consecutive iters
    # -----------------------------------------------------------------------

    def test_stagnation_triggers_rollback(self, tmp_path: pathlib.Path) -> None:
        """Error count stays same for 2 consecutive iters → rollback, ok=False."""
        spec_dir, git_root, repo_root = make_spec_dir(tmp_path)

        # Need spec file for snapshot to succeed
        findings = [{"code": "E100", "message": "err", "file": "spec/04_fr_list.json"}]
        failing = ([], _failing_ctx(findings))

        adapter = MockAdapter([_edit_response()] * 5)

        spec_check_results = [failing, failing, failing]  # never shrinks

        with patch(SPEC_CHECK_PATH, side_effect=spec_check_results), \
             patch("specdev_tools.llm.loop_outer.json_patch"):

            result = run_outer_loop(
                task=_TASK,
                validated_pointers=_VALIDATED_POINTERS,
                step_structure_summary=_STEP_SUMMARY,
                adapter=adapter,
                repo_root=repo_root,
                spec_dir=spec_dir,
                git_root=git_root,
                max_iters=5,
            )

        assert result["ok"] is False
        assert result["applied"] is False
        assert result["files_changed"] == []
        assert result["partial"] is True
        # Should have stopped after 3 iters (iter 1: set prev; iter 2: stall_count=1; iter 3: stall_count=2)
        assert result["iterations"] == 3

    # -----------------------------------------------------------------------
    # 5. Max iters exhausted → rollback, ok=False
    # -----------------------------------------------------------------------

    def test_max_iters_exhausted_rollback(self, tmp_path: pathlib.Path) -> None:
        """All iters fail spec-check → max_iters exhausted → rollback, ok=False."""
        spec_dir, git_root, repo_root = make_spec_dir(tmp_path)

        findings = [{"code": "E100", "message": "err", "file": "spec/04_fr_list.json"}]
        # Use shrinking counts to avoid stagnation: 3, 2, 1 (never reaches 0)
        def make_ctx(n: int) -> dict[str, Any]:
            return {"checks": {"schema": {"status": "FAIL", "error_count": n, "warning_count": 0, "findings": findings[:n]}}}

        spec_check_results = [([], make_ctx(3)), ([], make_ctx(2)), ([], make_ctx(1))]
        adapter = MockAdapter([_edit_response()] * 3)

        with patch(SPEC_CHECK_PATH, side_effect=spec_check_results), \
             patch("specdev_tools.llm.loop_outer.json_patch"):

            result = run_outer_loop(
                task=_TASK,
                validated_pointers=_VALIDATED_POINTERS,
                step_structure_summary=_STEP_SUMMARY,
                adapter=adapter,
                repo_root=repo_root,
                spec_dir=spec_dir,
                git_root=git_root,
                max_iters=3,
            )

        assert result["ok"] is False
        assert result["applied"] is False
        assert result["files_changed"] == []
        assert result["iterations"] == 3
        assert result["partial"] is True

    # -----------------------------------------------------------------------
    # 6. Invalid JSON response → discard, continues
    # -----------------------------------------------------------------------

    def test_invalid_json_response_discard_continues(self, tmp_path: pathlib.Path) -> None:
        """Invalid JSON response → discard (no rollback), iteration continues."""
        spec_dir, git_root, repo_root = make_spec_dir(tmp_path)

        adapter = MockAdapter(["not valid json {{{", _edit_response()])

        with patch(SPEC_CHECK_PATH, return_value=([], _clean_ctx())), \
             patch("specdev_tools.llm.loop_outer.json_patch"):

            result = run_outer_loop(
                task=_TASK,
                validated_pointers=_VALIDATED_POINTERS,
                step_structure_summary=_STEP_SUMMARY,
                adapter=adapter,
                repo_root=repo_root,
                spec_dir=spec_dir,
                git_root=git_root,
                max_iters=5,
            )

        # Second response was valid and clean
        assert result["ok"] is True
        assert result["iterations"] == 2  # 1 discard + 1 clean

    # -----------------------------------------------------------------------
    # 7. Schema violation response → discard, continues
    # -----------------------------------------------------------------------

    def test_schema_violation_response_discard_continues(self, tmp_path: pathlib.Path) -> None:
        """Schema-invalid response → discard, loop continues to next iter."""
        spec_dir, git_root, repo_root = make_spec_dir(tmp_path)

        # Schema violation: edits is missing required fields
        bad_response = json.dumps({"edits": [{"file": "x", "wrong_field": "y"}], "rationale": "r"})
        adapter = MockAdapter([bad_response, _edit_response()])

        with patch(SPEC_CHECK_PATH, return_value=([], _clean_ctx())), \
             patch("specdev_tools.llm.loop_outer.json_patch"):

            result = run_outer_loop(
                task=_TASK,
                validated_pointers=_VALIDATED_POINTERS,
                step_structure_summary=_STEP_SUMMARY,
                adapter=adapter,
                repo_root=repo_root,
                spec_dir=spec_dir,
                git_root=git_root,
                max_iters=5,
            )

        assert result["ok"] is True
        assert result["iterations"] == 2  # 1 discard + 1 valid

    # -----------------------------------------------------------------------
    # 8. Rollback leaves no residue (files restored to snapshot state)
    # -----------------------------------------------------------------------

    def test_rollback_restores_original_file_content(self, tmp_path: pathlib.Path) -> None:
        """On rollback, the original spec file content is restored."""
        spec_dir, git_root, repo_root = make_spec_dir(tmp_path)

        original_content = (pathlib.Path(spec_dir) / "04_fr_list.json").read_text(encoding="utf-8")

        # Edits will actually mutate the file; spec-check fails; stagnation → rollback
        findings = [{"code": "E100", "message": "err", "file": "spec/04_fr_list.json"}]
        failing_ctx = _failing_ctx(findings)

        def mutating_patch(file_abs: str, _jq_path: str, _value_str: str) -> None:
            """Simulate an edit that changes the file."""
            data = json.loads(pathlib.Path(file_abs).read_text(encoding="utf-8"))
            data["mutated_by_test"] = True
            pathlib.Path(file_abs).write_text(json.dumps(data), encoding="utf-8")

        adapter = MockAdapter([_edit_response()] * 5)

        with patch(SPEC_CHECK_PATH, return_value=([], failing_ctx)), \
             patch("specdev_tools.llm.loop_outer.json_patch", side_effect=mutating_patch):

            result = run_outer_loop(
                task=_TASK,
                validated_pointers=_VALIDATED_POINTERS,
                step_structure_summary=_STEP_SUMMARY,
                adapter=adapter,
                repo_root=repo_root,
                spec_dir=spec_dir,
                git_root=git_root,
                max_iters=5,
            )

        assert result["applied"] is False

        # File must be restored to original content
        restored_content = (pathlib.Path(spec_dir) / "04_fr_list.json").read_text(encoding="utf-8")
        assert json.loads(restored_content) == json.loads(original_content), (
            "Rollback did not restore original file content"
        )
        assert "mutated_by_test" not in json.loads(restored_content)

    # -----------------------------------------------------------------------
    # 9. Forward-replay flag set when upstream file edited
    # -----------------------------------------------------------------------

    def test_forward_replay_flag_set_for_upstream_edit(self, tmp_path: pathlib.Path) -> None:
        """When edit touches step 04 (not last), include_forward_replay=True is passed."""
        spec_dir, git_root, repo_root = make_spec_dir(tmp_path)
        # step_order has 16c as last; 04 is upstream
        import specdev_tools.llm.loop_outer as lo
        lo._STEP_ORDER_CACHE = {}

        adapter = MockAdapter([_edit_response("spec/04_fr_list.json")])

        spec_check_calls: list[dict[str, Any]] = []

        def capturing_spec_check(
            repo_root_: str,
            spec_dir_: str,
            include_forward_replay: bool = False,
            **kwargs: Any,
        ) -> tuple[list[Any], dict[str, Any]]:
            spec_check_calls.append({"include_forward_replay": include_forward_replay})
            return [], _clean_ctx()

        with patch(SPEC_CHECK_PATH, side_effect=capturing_spec_check), \
             patch("specdev_tools.llm.loop_outer.json_patch"):

            result = run_outer_loop(
                task=_TASK,
                validated_pointers=_VALIDATED_POINTERS,
                step_structure_summary=_STEP_SUMMARY,
                adapter=adapter,
                repo_root=repo_root,
                spec_dir=spec_dir,
                git_root=git_root,
                max_iters=5,
            )

        assert result["ok"] is True
        assert len(spec_check_calls) == 1
        assert spec_check_calls[0]["include_forward_replay"] is True

    # -----------------------------------------------------------------------
    # 10. Forward-replay NOT set for last step
    # -----------------------------------------------------------------------

    def test_no_forward_replay_for_final_step_edit(self, tmp_path: pathlib.Path) -> None:
        """When edit touches last step (16c), include_forward_replay=False."""
        spec_dir, git_root, repo_root = make_spec_dir(tmp_path)
        import specdev_tools.llm.loop_outer as lo
        lo._STEP_ORDER_CACHE = {}

        # Create a 16c spec file
        (pathlib.Path(spec_dir) / "16c_review.json").write_text(
            json.dumps({"$schema": "x", "id": "16c"}), encoding="utf-8"
        )
        final_step_pointers = [{"file": "spec/16c_review.json", "id": "some-id"}]

        adapter = MockAdapter([_edit_response("spec/16c_review.json")])

        spec_check_calls: list[dict[str, Any]] = []

        def capturing_spec_check(
            repo_root_: str,
            spec_dir_: str,
            include_forward_replay: bool = False,
            **kwargs: Any,
        ) -> tuple[list[Any], dict[str, Any]]:
            spec_check_calls.append({"include_forward_replay": include_forward_replay})
            return [], _clean_ctx()

        with patch(SPEC_CHECK_PATH, side_effect=capturing_spec_check), \
             patch("specdev_tools.llm.loop_outer.json_patch"):

            result = run_outer_loop(
                task=_TASK,
                validated_pointers=final_step_pointers,
                step_structure_summary=_STEP_SUMMARY,
                adapter=adapter,
                repo_root=repo_root,
                spec_dir=spec_dir,
                git_root=git_root,
                max_iters=5,
            )

        assert result["ok"] is True
        assert spec_check_calls[0]["include_forward_replay"] is False

    # -----------------------------------------------------------------------
    # 11. snapshot_id reflects touched steps
    # -----------------------------------------------------------------------

    def test_snapshot_id_contains_step(self, tmp_path: pathlib.Path) -> None:
        """snapshot_id has the snap-<step>-<ts>-<hash> format per §15."""
        spec_dir, git_root, repo_root = make_spec_dir(tmp_path)
        adapter = MockAdapter([_edit_response()])

        with patch(SPEC_CHECK_PATH, return_value=([], _clean_ctx())), \
             patch("specdev_tools.llm.loop_outer.json_patch"):

            result = run_outer_loop(
                task=_TASK,
                validated_pointers=_VALIDATED_POINTERS,  # file: spec/04_fr_list.json
                step_structure_summary=_STEP_SUMMARY,
                adapter=adapter,
                repo_root=repo_root,
                spec_dir=spec_dir,
                git_root=git_root,
                max_iters=5,
            )

        sid = result["snapshot_id"]
        # Must contain the step ID and follow the sortable unique format
        assert "04" in sid
        assert sid.startswith("snap-04-"), f"snapshot_id format wrong: {sid!r}"
        # Four parts: snap, step, timestamp, hash
        parts = sid.split("-")
        assert len(parts) >= 4, f"snapshot_id must have at least 4 dash-segments: {sid!r}"

    # -----------------------------------------------------------------------
    # 12. files_changed is empty on rollback
    # -----------------------------------------------------------------------

    def test_files_changed_empty_on_rollback(self, tmp_path: pathlib.Path) -> None:
        """After rollback, files_changed is []."""
        spec_dir, git_root, repo_root = make_spec_dir(tmp_path)
        adapter = MockAdapter([_edit_response()] * 5)

        findings = [{"code": "E100", "message": "err", "file": "spec/04_fr_list.json"}]
        failing_ctx = _failing_ctx(findings)

        with patch(SPEC_CHECK_PATH, return_value=([], failing_ctx)), \
             patch("specdev_tools.llm.loop_outer.json_patch"):

            result = run_outer_loop(
                task=_TASK,
                validated_pointers=_VALIDATED_POINTERS,
                step_structure_summary=_STEP_SUMMARY,
                adapter=adapter,
                repo_root=repo_root,
                spec_dir=spec_dir,
                git_root=git_root,
                max_iters=5,
            )

        assert result["files_changed"] == []

    # -----------------------------------------------------------------------
    # 13. partial=True iff unresolved non-empty
    # -----------------------------------------------------------------------

    def test_partial_contract(self, tmp_path: pathlib.Path) -> None:
        """partial is True iff unresolved is non-empty (contract check)."""
        spec_dir, git_root, repo_root = make_spec_dir(tmp_path)
        adapter = MockAdapter([_edit_response()])

        with patch(SPEC_CHECK_PATH, return_value=([], _clean_ctx())), \
             patch("specdev_tools.llm.loop_outer.json_patch"):

            result = run_outer_loop(
                task=_TASK,
                validated_pointers=_VALIDATED_POINTERS,
                step_structure_summary=_STEP_SUMMARY,
                adapter=adapter,
                repo_root=repo_root,
                spec_dir=spec_dir,
                git_root=git_root,
                max_iters=5,
            )

        # ok=True path: partial=False, unresolved=[]
        assert result["partial"] == (len(result["unresolved"]) > 0)
        assert result["partial"] is False

    def test_partial_contract_on_failure(self, tmp_path: pathlib.Path) -> None:
        """partial=True iff unresolved non-empty on failure path."""
        spec_dir, git_root, repo_root = make_spec_dir(tmp_path)
        adapter = MockAdapter([_edit_response()] * 5)
        findings = [{"code": "E100", "message": "err"}]

        with patch(SPEC_CHECK_PATH, return_value=([], _failing_ctx(findings))), \
             patch("specdev_tools.llm.loop_outer.json_patch"):

            result = run_outer_loop(
                task=_TASK,
                validated_pointers=_VALIDATED_POINTERS,
                step_structure_summary=_STEP_SUMMARY,
                adapter=adapter,
                repo_root=repo_root,
                spec_dir=spec_dir,
                git_root=git_root,
                max_iters=5,
            )

        assert result["partial"] == (len(result["unresolved"]) > 0)
        assert result["partial"] is True

    # -----------------------------------------------------------------------
    # 14. max_iters=None reads from env var via config
    # -----------------------------------------------------------------------

    def test_max_iters_none_reads_from_config(self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """max_iters=None reads SPECDEV_LLM_MAX_ITERS from env via get_config."""
        spec_dir, git_root, repo_root = make_spec_dir(tmp_path)
        monkeypatch.setenv("SPECDEV_LLM_MAX_ITERS", "1")
        reset_config()

        findings = [{"code": "E100", "message": "err"}]
        adapter = MockAdapter([_edit_response()] * 10)

        with patch(SPEC_CHECK_PATH, return_value=([], _failing_ctx(findings))), \
             patch("specdev_tools.llm.loop_outer.json_patch"):

            result = run_outer_loop(
                task=_TASK,
                validated_pointers=_VALIDATED_POINTERS,
                step_structure_summary=_STEP_SUMMARY,
                adapter=adapter,
                repo_root=repo_root,
                spec_dir=spec_dir,
                git_root=git_root,
                max_iters=None,
            )

        # With max_iters=1 and always-failing spec-check, should exhaust after 1 iter
        assert result["iterations"] == 1
        assert result["ok"] is False

    # -----------------------------------------------------------------------
    # 15. Discards with no findings → sentinel injected
    # -----------------------------------------------------------------------

    def test_all_discards_injects_sentinel(self, tmp_path: pathlib.Path) -> None:
        """When all iters are discards, a sentinel is injected in unresolved."""
        spec_dir, git_root, repo_root = make_spec_dir(tmp_path)
        adapter = MockAdapter(["bad json", "bad json", "bad json"])

        result = run_outer_loop(
            task=_TASK,
            validated_pointers=_VALIDATED_POINTERS,
            step_structure_summary=_STEP_SUMMARY,
            adapter=adapter,
            repo_root=repo_root,
            spec_dir=spec_dir,
            git_root=git_root,
            max_iters=3,
        )

        assert result["ok"] is False
        assert result["partial"] is True
        assert result["unresolved"]  # sentinel present
        assert any("discarded" in u.get("reason", "") for u in result["unresolved"])


# ---------------------------------------------------------------------------
# Snapshot / restore integration tests
# ---------------------------------------------------------------------------

class TestRestoreSnapshot:

    def test_restore_snapshot_round_trip(self, tmp_path: pathlib.Path) -> None:
        """save_snapshot → mutate → restore_snapshot returns original content."""
        spec_dir, _git_root, repo_root = make_spec_dir(tmp_path)

        # Save snapshot
        save_result = save_snapshot(step_id="04", spec_dir=spec_dir, _repo_root=repo_root)
        assert save_result["status"] == "saved"

        # Mutate the file
        spec_file = pathlib.Path(spec_dir) / "04_fr_list.json"
        original = json.loads(spec_file.read_text(encoding="utf-8"))
        mutated = dict(original, mutated=True)
        spec_file.write_text(json.dumps(mutated), encoding="utf-8")

        # Restore
        restore_result = restore_snapshot(step_id="04", spec_dir=spec_dir)
        assert restore_result["status"] == "restored"

        # Content should match original
        restored = json.loads(spec_file.read_text(encoding="utf-8"))
        assert restored == original
        assert "mutated" not in restored

    def test_restore_snapshot_not_found(self, tmp_path: pathlib.Path) -> None:
        """restore_snapshot returns not_found when no snapshot exists."""
        spec_dir, _git_root, repo_root = make_spec_dir(tmp_path)

        result = restore_snapshot(step_id="99", spec_dir=spec_dir)
        assert result["status"] == "not_found"

    def test_restore_snapshot_artifact_absent(self, tmp_path: pathlib.Path) -> None:
        """restore_snapshot returns not_found when snapshot exists but artifact is gone."""
        spec_dir, _git_root, repo_root = make_spec_dir(tmp_path)

        # Save a valid snapshot for step 04
        save_snapshot(step_id="04", spec_dir=spec_dir, _repo_root=repo_root)

        # Delete the artifact (simulates mid-loop file deletion)
        spec_file = pathlib.Path(spec_dir) / "04_fr_list.json"
        spec_file.unlink()

        # restore_snapshot cannot find the artifact to write into
        result = restore_snapshot(step_id="04", spec_dir=spec_dir)
        assert result["status"] == "not_found"


# ---------------------------------------------------------------------------
# Additional tests for findings from the deep review
# ---------------------------------------------------------------------------

class TestApplyErrorRollback:
    """MEDIUM: apply failure → immediate rollback, spec_check_status=NOT_RUN."""

    def test_apply_error_triggers_rollback_and_not_run_status(
        self, tmp_path: pathlib.Path
    ) -> None:
        spec_dir, git_root, repo_root = make_spec_dir(tmp_path)
        import specdev_tools.llm.loop_outer as lo
        lo._STEP_ORDER_CACHE = {}

        adapter = MockAdapter([_edit_response()])

        with patch(SPEC_CHECK_PATH) as mock_sc, \
             patch(
                 "specdev_tools.llm.loop_outer.json_patch",
                 side_effect=RuntimeError("jq failed: bad path"),
             ):
            result = run_outer_loop(
                task=_TASK,
                validated_pointers=_VALIDATED_POINTERS,
                step_structure_summary=_STEP_SUMMARY,
                adapter=adapter,
                repo_root=repo_root,
                spec_dir=spec_dir,
                git_root=git_root,
                max_iters=5,
            )

        # spec-check must NOT have been called — apply failed before we reached it
        mock_sc.assert_not_called()
        assert result["ok"] is False
        assert result["applied"] is False
        assert result["files_changed"] == []
        assert result["spec_check_status"] == "NOT_RUN"
        assert any("apply error" in u.get("reason", "") for u in result["unresolved"])
        # spec_check key present with empty forward_replay
        assert result["spec_check"]["forward_replay"] == []


class TestFilesChangedOnSuccess:
    """MEDIUM: files_changed contains the mutated paths on success."""

    def test_files_changed_contains_absolute_path(self, tmp_path: pathlib.Path) -> None:
        spec_dir, git_root, repo_root = make_spec_dir(tmp_path)
        import specdev_tools.llm.loop_outer as lo
        lo._STEP_ORDER_CACHE = {}

        patched_files: list[str] = []

        def recording_patch(file_abs: str, _jq: str, _val: str, **_kw: Any) -> None:
            patched_files.append(file_abs)

        adapter = MockAdapter([_edit_response()])

        with patch(SPEC_CHECK_PATH, return_value=([], _clean_ctx())), \
             patch("specdev_tools.llm.loop_outer.json_patch", side_effect=recording_patch):

            result = run_outer_loop(
                task=_TASK,
                validated_pointers=_VALIDATED_POINTERS,
                step_structure_summary=_STEP_SUMMARY,
                adapter=adapter,
                repo_root=repo_root,
                spec_dir=spec_dir,
                git_root=git_root,
                max_iters=5,
            )

        assert result["ok"] is True
        assert len(result["files_changed"]) > 0
        assert result["files_changed"] == sorted(patched_files)


class TestSpecCheckStatusOnFailure:
    """MEDIUM: spec_check_status is 'FAIL' on failure paths."""

    def test_spec_check_status_fail_on_stagnation(self, tmp_path: pathlib.Path) -> None:
        spec_dir, git_root, repo_root = make_spec_dir(tmp_path)
        adapter = MockAdapter([_edit_response()] * 10)

        with patch(SPEC_CHECK_PATH, return_value=([], _failing_ctx())), \
             patch("specdev_tools.llm.loop_outer.json_patch"):

            result = run_outer_loop(
                task=_TASK,
                validated_pointers=_VALIDATED_POINTERS,
                step_structure_summary=_STEP_SUMMARY,
                adapter=adapter,
                repo_root=repo_root,
                spec_dir=spec_dir,
                git_root=git_root,
                max_iters=5,
            )

        assert result["spec_check_status"] == "FAIL"

    def test_spec_check_status_fail_on_max_iters_exhausted(
        self, tmp_path: pathlib.Path
    ) -> None:
        spec_dir, git_root, repo_root = make_spec_dir(tmp_path)
        adapter = MockAdapter([_edit_response()] * 2)

        with patch(SPEC_CHECK_PATH, return_value=([], _failing_ctx())), \
             patch("specdev_tools.llm.loop_outer.json_patch"):

            result = run_outer_loop(
                task=_TASK,
                validated_pointers=_VALIDATED_POINTERS,
                step_structure_summary=_STEP_SUMMARY,
                adapter=adapter,
                repo_root=repo_root,
                spec_dir=spec_dir,
                git_root=git_root,
                max_iters=2,
            )

        assert result["spec_check_status"] == "FAIL"
        assert result["iterations"] == 2

    def test_spec_check_status_warn_when_only_warnings(
        self, tmp_path: pathlib.Path
    ) -> None:
        """When spec-check has only warnings (no errors), status is WARN, loop still exits clean."""
        spec_dir, git_root, repo_root = make_spec_dir(tmp_path)
        adapter = MockAdapter([_edit_response()])

        warn_ctx = {
            "checks": {
                "schema": {
                    "status": "WARN",
                    "error_count": 0,
                    "warning_count": 1,
                    "findings": [{"code": "W100", "message": "a warning"}],
                }
            }
        }

        with patch(SPEC_CHECK_PATH, return_value=([], warn_ctx)), \
             patch("specdev_tools.llm.loop_outer.json_patch"):

            result = run_outer_loop(
                task=_TASK,
                validated_pointers=_VALIDATED_POINTERS,
                step_structure_summary=_STEP_SUMMARY,
                adapter=adapter,
                repo_root=repo_root,
                spec_dir=spec_dir,
                git_root=git_root,
                max_iters=5,
            )

        # Warnings don't block; loop exits clean but status reflects WARN
        assert result["ok"] is True
        assert result["spec_check_status"] == "WARN"


class TestSpecCheckForwardReplayKey:
    """HIGH: spec_check.forward_replay key present in all return paths."""

    def test_forward_replay_key_present_on_success(self, tmp_path: pathlib.Path) -> None:
        spec_dir, git_root, repo_root = make_spec_dir(tmp_path)
        adapter = MockAdapter([_edit_response()])

        with patch(SPEC_CHECK_PATH, return_value=([], _clean_ctx())), \
             patch("specdev_tools.llm.loop_outer.json_patch"):

            result = run_outer_loop(
                task=_TASK,
                validated_pointers=_VALIDATED_POINTERS,
                step_structure_summary=_STEP_SUMMARY,
                adapter=adapter,
                repo_root=repo_root,
                spec_dir=spec_dir,
                git_root=git_root,
                max_iters=5,
            )

        assert "spec_check" in result
        assert "forward_replay" in result["spec_check"]
        assert isinstance(result["spec_check"]["forward_replay"], list)

    def test_forward_replay_key_present_on_rollback(self, tmp_path: pathlib.Path) -> None:
        spec_dir, git_root, repo_root = make_spec_dir(tmp_path)
        adapter = MockAdapter([_edit_response()] * 10)

        with patch(SPEC_CHECK_PATH, return_value=([], _failing_ctx())), \
             patch("specdev_tools.llm.loop_outer.json_patch"):

            result = run_outer_loop(
                task=_TASK,
                validated_pointers=_VALIDATED_POINTERS,
                step_structure_summary=_STEP_SUMMARY,
                adapter=adapter,
                repo_root=repo_root,
                spec_dir=spec_dir,
                git_root=git_root,
                max_iters=5,
            )

        assert "spec_check" in result
        assert "forward_replay" in result["spec_check"]

    def test_forward_replay_findings_surfaced(self, tmp_path: pathlib.Path) -> None:
        """forward_replay findings from spec-check are passed through to spec_check key."""
        spec_dir, git_root, repo_root = make_spec_dir(tmp_path)
        adapter = MockAdapter([_edit_response()])

        replay_ctx = {
            "checks": {
                "schema": {"status": "PASS", "error_count": 0, "warning_count": 0, "findings": []},
                "forward-replay-check": {
                    "status": "FAIL",
                    "error_count": 1,
                    "warning_count": 0,
                    "findings": [{"code": "E550", "message": "replay drift detected"}],
                },
            }
        }
        # Spec errors from forward replay → loop fails
        replay_spec_errors = [object()]  # non-empty → has_errors=True

        with patch(SPEC_CHECK_PATH, return_value=(replay_spec_errors, replay_ctx)), \
             patch("specdev_tools.llm.loop_outer.json_patch"):

            result = run_outer_loop(
                task=_TASK,
                validated_pointers=_VALIDATED_POINTERS,
                step_structure_summary=_STEP_SUMMARY,
                adapter=adapter,
                repo_root=repo_root,
                spec_dir=spec_dir,
                git_root=git_root,
                max_iters=1,
            )

        assert result["spec_check"]["forward_replay"] == [
            {"code": "E550", "message": "replay drift detected"}
        ]


class TestLateSnapshotCoverage:
    """CRITICAL: LLM edits outside validated_pointers are snapshotted before mutation."""

    def test_edit_outside_pointers_is_snapshotted(self, tmp_path: pathlib.Path) -> None:
        """An edit targeting a file not in validated_pointers must be snapshotted."""
        spec_dir, git_root, repo_root = make_spec_dir(tmp_path)
        import specdev_tools.llm.loop_outer as lo
        lo._STEP_ORDER_CACHE = {}

        # Create a second spec file (step 05) not referenced in validated_pointers
        (pathlib.Path(spec_dir) / "05_interface_contracts.json").write_text(
            json.dumps({"$schema": "x", "id": "05", "interfaces": []}), encoding="utf-8"
        )

        # The LLM proposes an edit to spec/05_interface_contracts.json (outside pointers)
        edit_response = json.dumps({
            "edits": [
                {"file": "spec/05_interface_contracts.json",
                 "jq_path": ".interfaces",
                 "value": []}
            ],
            "rationale": "Clears interfaces.",
        })
        adapter = MockAdapter([edit_response])
        snapshotted: list[str] = []

        real_save_snapshot = __import__(
            "specdev_tools.context.snapshot", fromlist=["save_snapshot"]
        ).save_snapshot

        def recording_save(step_id: str, spec_dir: str, _repo_root: str) -> dict[str, Any]:
            snapshotted.append(step_id)
            return real_save_snapshot(step_id=step_id, spec_dir=spec_dir, _repo_root=_repo_root)

        with patch(SPEC_CHECK_PATH, return_value=([], _clean_ctx())), \
             patch("specdev_tools.llm.loop_outer.json_patch"), \
             patch("specdev_tools.llm.loop_outer.save_snapshot", side_effect=recording_save):

            result = run_outer_loop(
                task=_TASK,
                validated_pointers=_VALIDATED_POINTERS,  # only spec/04_fr_list.json
                step_structure_summary=_STEP_SUMMARY,
                adapter=adapter,
                repo_root=repo_root,
                spec_dir=spec_dir,
                git_root=git_root,
                max_iters=5,
            )

        # Step 05 must have been snapshotted even though it wasn't in validated_pointers
        assert "05" in snapshotted, (
            f"Step 05 should have been late-snapshotted; got snapshotted={snapshotted}"
        )


# ---------------------------------------------------------------------------
# Pass-3 review fixes
# ---------------------------------------------------------------------------


class TestDryRunMode:
    """F10: SPECDEV_LLM_DRY_RUN=1 → no LLM calls, no mutations, honest partial return."""

    def setup_method(self) -> None:
        reset_config()
        import specdev_tools.llm.loop_outer as lo
        lo._STEP_ORDER_CACHE = {}
        lo._SCHEMA_CACHE = None
        lo._TEMPLATE_CACHE.clear()

    def test_dry_run_returns_no_op_immediately(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        spec_dir, git_root, repo_root = make_spec_dir(tmp_path)
        monkeypatch.setenv("SPECDEV_LLM_DRY_RUN", "1")
        reset_config()

        adapter = MockAdapter(["should not be called"])

        with patch(SPEC_CHECK_PATH) as mock_sc, \
             patch("specdev_tools.llm.loop_outer.save_snapshot") as mock_snap:

            result = run_outer_loop(
                task=_TASK,
                validated_pointers=_VALIDATED_POINTERS,
                step_structure_summary=_STEP_SUMMARY,
                adapter=adapter,
                repo_root=repo_root,
                spec_dir=spec_dir,
                git_root=git_root,
            )

        assert result["ok"] is False
        assert result["applied"] is False
        assert result["iterations"] == 0
        assert result["files_changed"] == []
        assert result["snapshot_id"] == ""
        assert any("LLM_DRY_RUN" in u.get("reason", "") for u in result["unresolved"])
        assert "spec_check" in result
        assert result["spec_check"]["forward_replay"] == []
        # No side effects: no LLM calls, no snapshots, no spec-check
        assert adapter.call_count == 0
        mock_sc.assert_not_called()
        mock_snap.assert_not_called()


class TestOneStepConstraint:
    """F8: validated_pointers spanning > 1 step must be rejected (§5.2 one-step rule)."""

    def setup_method(self) -> None:
        reset_config()
        import specdev_tools.llm.loop_outer as lo
        lo._STEP_ORDER_CACHE = {}
        lo._SCHEMA_CACHE = None
        lo._TEMPLATE_CACHE.clear()

    def test_multi_step_pointers_rejected(self, tmp_path: pathlib.Path) -> None:
        spec_dir, git_root, repo_root = make_spec_dir(tmp_path)

        multi_step_pointers = [
            {"file": "spec/04_fr_list.json", "id": "fr-example-001"},
            {"file": "spec/05_interface_contracts.json", "id": "api-foo"},
        ]
        adapter = MockAdapter(["should not be called"])

        with patch(SPEC_CHECK_PATH) as mock_sc, \
             patch("specdev_tools.llm.loop_outer.save_snapshot") as mock_snap:

            result = run_outer_loop(
                task=_TASK,
                validated_pointers=multi_step_pointers,
                step_structure_summary=_STEP_SUMMARY,
                adapter=adapter,
                repo_root=repo_root,
                spec_dir=spec_dir,
                git_root=git_root,
                max_iters=5,
            )

        assert result["ok"] is False
        assert result["iterations"] == 0
        assert any("one step" in u.get("reason", "").lower() or "span" in u.get("reason", "").lower()
                   for u in result["unresolved"])
        # No snapshots or LLM calls should be made
        mock_snap.assert_not_called()
        mock_sc.assert_not_called()
        assert adapter.call_count == 0


class TestSnapshotFailureFastExit:
    """F15/Gap E: snapshot failure for any step → hard error, no LLM calls."""

    def setup_method(self) -> None:
        reset_config()
        import specdev_tools.llm.loop_outer as lo
        lo._STEP_ORDER_CACHE = {}
        lo._SCHEMA_CACHE = None
        lo._TEMPLATE_CACHE.clear()

    def test_snapshot_failure_returns_error_immediately(self, tmp_path: pathlib.Path) -> None:
        spec_dir, git_root, repo_root = make_spec_dir(tmp_path)
        adapter = MockAdapter(["should not be called"])

        def failing_save(step_id: str, spec_dir: str, _repo_root: str) -> dict[str, Any]:
            return {"step": step_id, "status": "not_found", "error": "no artifact"}

        with patch(SPEC_CHECK_PATH) as mock_sc, \
             patch("specdev_tools.llm.loop_outer.save_snapshot", side_effect=failing_save):

            result = run_outer_loop(
                task=_TASK,
                validated_pointers=_VALIDATED_POINTERS,
                step_structure_summary=_STEP_SUMMARY,
                adapter=adapter,
                repo_root=repo_root,
                spec_dir=spec_dir,
                git_root=git_root,
                max_iters=5,
            )

        assert result["ok"] is False
        assert result["applied"] is False
        assert result["iterations"] == 0
        assert any("snapshot failed" in u.get("reason", "").lower() for u in result["unresolved"])
        assert "spec_check" in result
        # No LLM calls should be made after snapshot failure
        assert adapter.call_count == 0
        mock_sc.assert_not_called()


class TestForwardReplayErrorCountDrivesHasErrors:
    """F23: forward-replay check error_count alone (spec_errors=[]) should drive has_errors."""

    def setup_method(self) -> None:
        reset_config()
        import specdev_tools.llm.loop_outer as lo
        lo._STEP_ORDER_CACHE = {}
        lo._SCHEMA_CACHE = None
        lo._TEMPLATE_CACHE.clear()

    def test_forward_replay_error_count_blocks_success(self, tmp_path: pathlib.Path) -> None:
        """spec_errors=[] but forward-replay-check.error_count=1 → has_errors=True, loop continues."""
        spec_dir, git_root, repo_root = make_spec_dir(tmp_path)
        import specdev_tools.llm.loop_outer as lo
        lo._STEP_ORDER_CACHE = {}

        # ctx with ONLY forward-replay errors; no spec_errors list
        replay_only_ctx = {
            "checks": {
                "schema": {"status": "PASS", "error_count": 0, "warning_count": 0, "findings": []},
                "forward-replay-check": {
                    "status": "FAIL",
                    "error_count": 1,
                    "warning_count": 0,
                    "findings": [{"code": "E555", "message": "replay drift"}],
                },
            }
        }

        # Two responses: first returns forward-replay errors, second is clean
        clean_ctx = _clean_ctx()
        spec_check_results = [
            ([], replay_only_ctx),  # first iter: forward-replay errors, no spec_errors
            ([], clean_ctx),        # second iter: clean
        ]

        adapter = MockAdapter([_edit_response(), _edit_response()])

        with patch(SPEC_CHECK_PATH, side_effect=spec_check_results), \
             patch("specdev_tools.llm.loop_outer.json_patch"):

            result = run_outer_loop(
                task=_TASK,
                validated_pointers=_VALIDATED_POINTERS,
                step_structure_summary=_STEP_SUMMARY,
                adapter=adapter,
                repo_root=repo_root,
                spec_dir=spec_dir,
                git_root=git_root,
                max_iters=5,
            )

        # Loop should NOT exit after iter 1 (forward-replay error blocked it)
        # and should exit clean on iter 2
        assert result["ok"] is True
        assert result["iterations"] == 2, (
            "Loop should have needed 2 iterations: forward-replay blocked iter 1"
        )


class TestNonStepFileEditRejected:
    """M2: LLM edits targeting non-step files (canon, seed) must be rejected — no snapshot path."""

    def setup_method(self) -> None:
        reset_config()
        import specdev_tools.llm.loop_outer as lo
        lo._STEP_ORDER_CACHE = {}
        lo._SCHEMA_CACHE = None
        lo._TEMPLATE_CACHE.clear()

    def test_non_step_file_edit_triggers_apply_error(self, tmp_path: pathlib.Path) -> None:
        """Edit targeting a file with no NN_ prefix → apply_error, rollback, ok=False."""
        spec_dir, git_root, repo_root = make_spec_dir(tmp_path)

        non_step_edit = json.dumps({
            "edits": [
                {"file": "canon/manifest.json", "jq_path": ".kinds", "value": []}
            ],
            "rationale": "Clear canon kinds.",
        })
        adapter = MockAdapter([non_step_edit])

        with patch(SPEC_CHECK_PATH) as mock_sc:
            result = run_outer_loop(
                task=_TASK,
                validated_pointers=_VALIDATED_POINTERS,
                step_structure_summary=_STEP_SUMMARY,
                adapter=adapter,
                repo_root=repo_root,
                spec_dir=spec_dir,
                git_root=git_root,
                max_iters=5,
            )

        assert result["ok"] is False
        assert result["applied"] is False
        assert result["files_changed"] == []
        assert any(
            "non-step" in u.get("reason", "").lower() or "NN_" in u.get("reason", "")
            for u in result["unresolved"]
        )
        # spec-check must NOT have been called (apply error exits before spec-check)
        mock_sc.assert_not_called()
        assert "spec_check" in result
        assert result["spec_check"]["forward_replay"] == []
        assert result["spec_check_status"] == "NOT_RUN"
        assert result["iterations"] == 1


class TestStagnationResetOnShrink:
    """Gap D: stall_count resets to 0 when error count shrinks."""

    def setup_method(self) -> None:
        reset_config()
        import specdev_tools.llm.loop_outer as lo
        lo._STEP_ORDER_CACHE = {}
        lo._SCHEMA_CACHE = None
        lo._TEMPLATE_CACHE.clear()

    def test_stagnation_reset_then_restagnates(self, tmp_path: pathlib.Path) -> None:
        """Error shrinks on iter 2 (stall_count→0), then stagnates on iters 3+4+5 → rollback."""
        spec_dir, git_root, repo_root = make_spec_dir(tmp_path)

        def make_ctx(n_errors: int) -> tuple[list[Any], dict[str, Any]]:
            findings = [{"code": "E100", "message": f"err{i}"} for i in range(n_errors)]
            return (
                [],
                {
                    "checks": {
                        "schema": {
                            "status": "FAIL" if n_errors else "PASS",
                            "error_count": n_errors,
                            "warning_count": 0,
                            "findings": findings,
                        }
                    }
                },
            )

        # Error counts: 3 → 2 (shrink, reset stall) → 2 → 2 (stall=1) → 2 (stall=2 → rollback)
        spec_check_results = [
            make_ctx(3),  # iter 1: prev=None → set prev=3
            make_ctx(2),  # iter 2: 2 < 3 → stall=0, set prev=2
            make_ctx(2),  # iter 3: 2 >= 2 → stall=1
            make_ctx(2),  # iter 4: 2 >= 2 → stall=2 → rollback
        ]
        adapter = MockAdapter([_edit_response()] * 5)

        with patch(SPEC_CHECK_PATH, side_effect=spec_check_results), \
             patch("specdev_tools.llm.loop_outer.json_patch"):

            result = run_outer_loop(
                task=_TASK,
                validated_pointers=_VALIDATED_POINTERS,
                step_structure_summary=_STEP_SUMMARY,
                adapter=adapter,
                repo_root=repo_root,
                spec_dir=spec_dir,
                git_root=git_root,
                max_iters=10,
            )

        assert result["ok"] is False
        assert result["applied"] is False
        # Stagnation fires on iteration 4 (after the shrink reset on iter 2)
        assert result["iterations"] == 4, (
            f"Expected stagnation on iter 4 after shrink-reset; got {result['iterations']}"
        )
