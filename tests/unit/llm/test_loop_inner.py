"""Unit tests for specdev_tools.llm.loop_inner — run_inner_loop.

All tests use tmp_path fixtures for synthetic spec dirs.
No dependency on the real host repo spec directory.
Synthetic ids follow the fr-example-NNN pattern.
"""
from __future__ import annotations

import json
import os
import pathlib
from collections import deque
from typing import Any

from specdev_tools.llm.loop_inner import _format_nearest, run_inner_loop

# ---------------------------------------------------------------------------
# Synthetic spec environment
# ---------------------------------------------------------------------------

_ENTRY_KEY_REGISTRY = {
    "registry": {
        "04_fr_list.json": {
            "step": "04",
            "arrays": [
                {
                    "array_path": ".functional_requirements",
                    "id_field": "fr_id",
                    "kind": "functional_requirement",
                }
            ],
        }
    }
}

_FR_LIST_SPEC = {
    "$schema": "vc:04-fr-list",
    "id": "fr-list",
    "owner": "product",
    "functional_requirements": [
        {"fr_id": "fr-example-001", "name": "First example requirement"},
        {"fr_id": "fr-example-002", "name": "Second example requirement"},
        {"fr_id": "fr-example-subscribe", "name": "Subscribe to newsletter"},
    ],
}


def make_spec_root(tmp_path: pathlib.Path) -> tuple[str, str]:
    """Build a minimal synthetic spec directory.

    Returns (spec_root_str, git_root_str).

    Layout:
        <tmp>/host/                      ← git_root
        <tmp>/host/spec/                 ← spec_root
        <tmp>/host/spec/entry_key_registry.json
        <tmp>/host/spec/04_fr_list.json
    """
    git_root = tmp_path / "host"
    git_root.mkdir(parents=True, exist_ok=True)
    spec = git_root / "spec"
    spec.mkdir()

    (spec / "entry_key_registry.json").write_text(
        json.dumps(_ENTRY_KEY_REGISTRY), encoding="utf-8"
    )
    (spec / "04_fr_list.json").write_text(
        json.dumps(_FR_LIST_SPEC), encoding="utf-8"
    )

    return str(spec), str(git_root)


# ---------------------------------------------------------------------------
# MockAdapter
# ---------------------------------------------------------------------------

class MockAdapter:
    """Queue-based mock LLMAdapter.

    Pops responses from a deque. Raises AssertionError if called more times
    than expected.
    """

    def __init__(self, responses: list[str]) -> None:
        self._queue: deque[str] = deque(responses)
        self.call_count = 0

    def chat(self, _system: str, _user: str) -> str:
        assert self._queue, (
            f"MockAdapter called too many times (already exhausted after "
            f"{self.call_count} call(s))"
        )
        self.call_count += 1
        return self._queue.popleft()


# ---------------------------------------------------------------------------
# Shared fixtures / constants
# ---------------------------------------------------------------------------

_TASK = "implement example-001 requirement"
_STEP_SUMMARY: dict[str, Any] = {
    "spec/04_fr_list.json": {
        "entry_count": 3,
        "ids": ["fr-example-001", "fr-example-002", "fr-example-subscribe"],
    }
}
_UPSTREAM: dict[str, Any] = {}
_PROMPT_NN = "# Prompt 04\nWrite functional requirements."

# Valid pointer responses (JSON strings the adapter returns)
_HAPPY_RESPONSE = json.dumps({
    "pointers": [
        {"file": "spec/04_fr_list.json", "id": "fr-example-001"},
    ],
    "unresolved": [],
})

_MISS_RESPONSE_1 = json.dumps({
    "pointers": [
        {"file": "spec/04_fr_list.json", "id": "fr-example-TYPO"},  # miss
    ],
    "unresolved": [],
})

_MISS_RESPONSE_A = json.dumps({
    "pointers": [
        {"file": "spec/04_fr_list.json", "id": "fr-no-such-A"},  # miss A
    ],
    "unresolved": [],
})

_MISS_RESPONSE_B = json.dumps({
    "pointers": [
        {"file": "spec/04_fr_list.json", "id": "fr-no-such-B"},  # miss B (same count, different set)
    ],
    "unresolved": [],
})

_MISS_RESPONSE_C = json.dumps({
    "pointers": [
        {"file": "spec/04_fr_list.json", "id": "fr-no-such-C"},  # miss C (third distinct set)
    ],
    "unresolved": [],
})



# ---------------------------------------------------------------------------
# Test class
# ---------------------------------------------------------------------------

class TestRunInnerLoop:

    def test_happy_path_empty_misses_on_iter1(self, tmp_path: pathlib.Path) -> None:
        """Iter 1 resolves all pointers cleanly → ok=True, iterations=1."""
        spec_root, git_root = make_spec_root(tmp_path)
        adapter = MockAdapter([_HAPPY_RESPONSE])
        result = run_inner_loop(
            task=_TASK,
            step_structure_summary=_STEP_SUMMARY,
            upstream_structure=_UPSTREAM,
            prompt_nn=_PROMPT_NN,
            adapter=adapter,
            spec_root=spec_root,
            git_root=git_root,
            max_iters=3,
        )
        assert result["ok"] is True
        assert result["partial"] is False
        assert result["iterations"] == 1
        assert result["unresolved"] == []
        assert len(result["validated_pointers"]) == 1
        assert adapter.call_count == 1

    def test_repair_fix_on_iter2(self, tmp_path: pathlib.Path) -> None:
        """Iter 1 has one miss; iter 2 fixes it → ok=True, iterations=2."""
        spec_root, git_root = make_spec_root(tmp_path)
        adapter = MockAdapter([_MISS_RESPONSE_1, _HAPPY_RESPONSE])
        result = run_inner_loop(
            task=_TASK,
            step_structure_summary=_STEP_SUMMARY,
            upstream_structure=_UPSTREAM,
            prompt_nn=_PROMPT_NN,
            adapter=adapter,
            spec_root=spec_root,
            git_root=git_root,
            max_iters=3,
        )
        assert result["ok"] is True
        assert result["partial"] is False
        assert result["iterations"] == 2
        assert result["unresolved"] == []

    def test_max_iters_reached_returns_partial(self, tmp_path: pathlib.Path) -> None:
        """3 iters with strictly decreasing misses → max_iters forces partial return.

        Miss counts: iter1=3, iter2=2, iter3=1. Each iter shrinks the miss set,
        so neither the same-set nor no-shrink stagnation condition fires.
        max_iters=3 is hit with one miss still remaining.
        """
        spec_root, git_root = make_spec_root(tmp_path)
        # Iter 1: 3 misses (all bad)
        r1 = json.dumps({"pointers": [
            {"file": "spec/04_fr_list.json", "id": "fr-bad-p"},
            {"file": "spec/04_fr_list.json", "id": "fr-bad-q"},
            {"file": "spec/04_fr_list.json", "id": "fr-bad-r"},
        ], "unresolved": []})
        # Iter 2: 2 misses — 1 fixed (fr-example-001 hit), 2 still bad
        r2 = json.dumps({"pointers": [
            {"file": "spec/04_fr_list.json", "id": "fr-example-001"},  # hit
            {"file": "spec/04_fr_list.json", "id": "fr-bad-q"},
            {"file": "spec/04_fr_list.json", "id": "fr-bad-r"},
        ], "unresolved": []})
        # Iter 3: 1 miss — another fixed (fr-example-002 hit), 1 still bad
        r3 = json.dumps({"pointers": [
            {"file": "spec/04_fr_list.json", "id": "fr-example-001"},  # hit
            {"file": "spec/04_fr_list.json", "id": "fr-example-002"},  # hit
            {"file": "spec/04_fr_list.json", "id": "fr-bad-r"},        # still a miss
        ], "unresolved": []})
        adapter = MockAdapter([r1, r2, r3])
        result = run_inner_loop(
            task=_TASK,
            step_structure_summary=_STEP_SUMMARY,
            upstream_structure=_UPSTREAM,
            prompt_nn=_PROMPT_NN,
            adapter=adapter,
            spec_root=spec_root,
            git_root=git_root,
            max_iters=3,
        )
        assert result["ok"] is False
        assert result["partial"] is True
        assert result["iterations"] == 3
        assert len(result["unresolved"]) >= 1

    def test_same_miss_set_twice_exits_early(self, tmp_path: pathlib.Path) -> None:
        """Iter 1: miss {A}, iter 2: miss {A} again → exits at iterations=2, partial=True."""
        spec_root, git_root = make_spec_root(tmp_path)
        adapter = MockAdapter([_MISS_RESPONSE_A, _MISS_RESPONSE_A])
        result = run_inner_loop(
            task=_TASK,
            step_structure_summary=_STEP_SUMMARY,
            upstream_structure=_UPSTREAM,
            prompt_nn=_PROMPT_NN,
            adapter=adapter,
            spec_root=spec_root,
            git_root=git_root,
            max_iters=3,
        )
        assert result["ok"] is False
        assert result["partial"] is True
        # Should exit early at iter 2, not continue to iter 3
        assert result["iterations"] == 2
        assert len(result["unresolved"]) >= 1

    def test_no_shrink_for_two_consecutive_exits_at_iter3(self, tmp_path: pathlib.Path) -> None:
        """Two consecutive non-shrinking transitions exits at iter 3, not iter 2.

        Trajectory: {A} → {B} → {C}. Count stays at 1 each iter; sets always
        differ so same-set (condition 2a) never fires.  After iter 2 only ONE
        stagnant transition has occurred (stall_count=1) — the loop must NOT
        exit.  After iter 3, stall_count=2 → condition 2b fires.
        """
        spec_root, git_root = make_spec_root(tmp_path)
        adapter = MockAdapter([_MISS_RESPONSE_A, _MISS_RESPONSE_B, _MISS_RESPONSE_C])
        result = run_inner_loop(
            task=_TASK,
            step_structure_summary=_STEP_SUMMARY,
            upstream_structure=_UPSTREAM,
            prompt_nn=_PROMPT_NN,
            adapter=adapter,
            spec_root=spec_root,
            git_root=git_root,
            max_iters=10,
        )
        assert result["ok"] is False
        assert result["partial"] is True
        # Must exit at iter 3 (two stagnant transitions), not iter 2 (one).
        assert result["iterations"] == 3

    def test_single_stagnant_transition_does_not_exit(self, tmp_path: pathlib.Path) -> None:
        """One stagnant transition followed by a shrink must NOT exit early.

        Trajectory: miss{A} (count=1) → miss{B} (count=1, stall=1) → ok (count=0).
        The loop must proceed past iter 2 (stall_count=1 < 2) and resolve on
        iter 3 via condition 1 (ok=True).  This is the regression test for the
        §5.1 "productive-but-non-strict-monotonic" protection.
        """
        spec_root, git_root = make_spec_root(tmp_path)
        adapter = MockAdapter([_MISS_RESPONSE_A, _MISS_RESPONSE_B, _HAPPY_RESPONSE])
        result = run_inner_loop(
            task=_TASK,
            step_structure_summary=_STEP_SUMMARY,
            upstream_structure=_UPSTREAM,
            prompt_nn=_PROMPT_NN,
            adapter=adapter,
            spec_root=spec_root,
            git_root=git_root,
            max_iters=10,
        )
        # Must NOT have exited early at iter 2; must resolve cleanly at iter 3.
        assert result["ok"] is True
        assert result["partial"] is False
        assert result["iterations"] == 3

    def test_llm_emits_content_field_discards_response(self, tmp_path: pathlib.Path) -> None:
        """A pointer with a 'content' field → response discarded, partial return."""
        spec_root, git_root = make_spec_root(tmp_path)
        # The schema enforces additionalProperties:false on pointer_item,
        # so a content field causes schema validation failure.
        # However, we also have an explicit content-field check.
        # Either path leads to discard.
        invalid_response = json.dumps({
            "pointers": [
                {
                    "file": "spec/04_fr_list.json",
                    "id": "fr-example-001",
                    "content": {"fr_id": "fr-example-001"},  # FORBIDDEN
                }
            ],
            "unresolved": [],
        })
        # After discard (max_iters=1), returns partial
        adapter = MockAdapter([invalid_response])
        result = run_inner_loop(
            task=_TASK,
            step_structure_summary=_STEP_SUMMARY,
            upstream_structure=_UPSTREAM,
            prompt_nn=_PROMPT_NN,
            adapter=adapter,
            spec_root=spec_root,
            git_root=git_root,
            max_iters=1,
        )
        # Response was discarded — no validated pointers should carry content
        for ptr in result.get("validated_pointers", []):
            assert "content" not in ptr, "content field leaked into validated_pointers"
        # With max_iters=1 and one discard, should be partial
        assert result["ok"] is False
        assert result["partial"] is True

    def test_llm_emits_invalid_json_discards_response(self, tmp_path: pathlib.Path) -> None:
        """Malformed JSON from LLM → response discarded, iteration counted."""
        spec_root, git_root = make_spec_root(tmp_path)
        malformed = "this is not valid json {"
        adapter = MockAdapter([malformed])
        result = run_inner_loop(
            task=_TASK,
            step_structure_summary=_STEP_SUMMARY,
            upstream_structure=_UPSTREAM,
            prompt_nn=_PROMPT_NN,
            adapter=adapter,
            spec_root=spec_root,
            git_root=git_root,
            max_iters=1,
        )
        assert result["ok"] is False
        assert result["partial"] is True
        assert result["iterations"] == 1

    def test_llm_response_fails_schema_discards_response(self, tmp_path: pathlib.Path) -> None:
        """Valid JSON that fails pointer_response.schema.json → response discarded."""
        spec_root, git_root = make_spec_root(tmp_path)
        # Missing required 'file' field on pointer item
        bad_schema_response = json.dumps({
            "pointers": [
                {"id": "fr-example-001"}  # missing required 'file'
            ],
            "unresolved": [],
        })
        adapter = MockAdapter([bad_schema_response])
        result = run_inner_loop(
            task=_TASK,
            step_structure_summary=_STEP_SUMMARY,
            upstream_structure=_UPSTREAM,
            prompt_nn=_PROMPT_NN,
            adapter=adapter,
            spec_root=spec_root,
            git_root=git_root,
            max_iters=1,
        )
        assert result["ok"] is False
        assert result["partial"] is True
        assert result["iterations"] == 1

    def test_unresolved_in_llm_response_honored(self, tmp_path: pathlib.Path) -> None:
        """LLM-emitted unresolved[] entries are preserved in the return value."""
        spec_root, git_root = make_spec_root(tmp_path)
        # LLM resolves one pointer cleanly but admits it can't find another
        response_with_llm_unresolved = json.dumps({
            "pointers": [
                {"file": "spec/04_fr_list.json", "id": "fr-example-001"},
            ],
            "unresolved": [
                {
                    "pointer": {"file": "spec/04_fr_list.json", "id": "fr-example-UNKNOWN"},
                    "reason": "could not find this ID in any spec file",
                }
            ],
        })
        adapter = MockAdapter([response_with_llm_unresolved])
        result = run_inner_loop(
            task=_TASK,
            step_structure_summary=_STEP_SUMMARY,
            upstream_structure=_UPSTREAM,
            prompt_nn=_PROMPT_NN,
            adapter=adapter,
            spec_root=spec_root,
            git_root=git_root,
            max_iters=1,
        )
        # The pointer fr-example-001 resolves, but the LLM also reported unresolved
        assert result["ok"] is False
        assert result["partial"] is True
        unresolved_ids = [
            u["pointer"].get("id") for u in result["unresolved"]
        ]
        assert "fr-example-UNKNOWN" in unresolved_ids

    def test_partial_return_includes_all_validated_pointers(
        self, tmp_path: pathlib.Path
    ) -> None:
        """On partial return, validated_pointers includes hits from last good iteration."""
        spec_root, git_root = make_spec_root(tmp_path)
        # Iter 1: one hit + one miss
        iter1_response = json.dumps({
            "pointers": [
                {"file": "spec/04_fr_list.json", "id": "fr-example-001"},  # hit
                {"file": "spec/04_fr_list.json", "id": "fr-no-such-Z"},    # miss
            ],
            "unresolved": [],
        })
        # Iter 2: same hit + same miss (stagnation exits here)
        iter2_response = json.dumps({
            "pointers": [
                {"file": "spec/04_fr_list.json", "id": "fr-example-001"},  # hit
                {"file": "spec/04_fr_list.json", "id": "fr-no-such-Z"},    # miss (same)
            ],
            "unresolved": [],
        })
        adapter = MockAdapter([iter1_response, iter2_response])
        result = run_inner_loop(
            task=_TASK,
            step_structure_summary=_STEP_SUMMARY,
            upstream_structure=_UPSTREAM,
            prompt_nn=_PROMPT_NN,
            adapter=adapter,
            spec_root=spec_root,
            git_root=git_root,
            max_iters=3,
        )
        assert result["ok"] is False
        assert result["partial"] is True
        # validated_pointers must include the hit
        validated_ids = [p.get("id") for p in result["validated_pointers"]]
        assert "fr-example-001" in validated_ids
        # unresolved must include the miss
        unresolved_ids = [u["pointer"].get("id") for u in result["unresolved"]]
        assert "fr-no-such-Z" in unresolved_ids

    def test_max_iters_1_terminates_immediately_on_miss(
        self, tmp_path: pathlib.Path
    ) -> None:
        """max_iters=1 with a miss → exits after 1 iteration, partial=True."""
        spec_root, git_root = make_spec_root(tmp_path)
        adapter = MockAdapter([_MISS_RESPONSE_1])
        result = run_inner_loop(
            task=_TASK,
            step_structure_summary=_STEP_SUMMARY,
            upstream_structure=_UPSTREAM,
            prompt_nn=_PROMPT_NN,
            adapter=adapter,
            spec_root=spec_root,
            git_root=git_root,
            max_iters=1,
        )
        assert result["ok"] is False
        assert result["partial"] is True
        assert result["iterations"] == 1
        assert len(result["unresolved"]) >= 1

    def test_max_iters_0_returns_partial(self, tmp_path: pathlib.Path) -> None:
        """max_iters=0 means no LLM calls are allowed → ok=False, partial=True.

        Reporting ok=True when no LLM calls were made would be semantically
        incorrect (no pointers were ever validated).
        """
        spec_root, git_root = make_spec_root(tmp_path)
        # Adapter should never be called; give it zero responses.
        adapter = MockAdapter([])
        result = run_inner_loop(
            task=_TASK,
            step_structure_summary=_STEP_SUMMARY,
            upstream_structure=_UPSTREAM,
            prompt_nn=_PROMPT_NN,
            adapter=adapter,
            spec_root=spec_root,
            git_root=git_root,
            max_iters=0,
        )
        assert result["ok"] is False
        assert result["partial"] is True
        assert result["iterations"] == 0
        assert result["validated_pointers"] == []
        assert len(result["unresolved"]) >= 1
        assert "max_iters=0" in result["unresolved"][0]["reason"]

    def test_unresolved_reason_preserves_resolve_pointers_signal(
        self, tmp_path: pathlib.Path
    ) -> None:
        """Partial return must carry the structured reason from resolve_pointers.

        Regression test for Finding 2 (first review): _partial_return used to
        reconstruct reason from nearest hints, silently dropping the structured
        reason (e.g. 'missing_path') that resolve_pointers already provided.
        """
        spec_root, git_root = make_spec_root(tmp_path)
        adapter = MockAdapter([_MISS_RESPONSE_1])
        result = run_inner_loop(
            task=_TASK,
            step_structure_summary=_STEP_SUMMARY,
            upstream_structure=_UPSTREAM,
            prompt_nn=_PROMPT_NN,
            adapter=adapter,
            spec_root=spec_root,
            git_root=git_root,
            max_iters=1,
        )
        assert result["ok"] is False
        assert result["partial"] is True
        assert len(result["unresolved"]) >= 1
        # The structured reason from resolve_pointers must be present.
        # For a typo-id miss, resolve_pointers emits reason='missing_path'.
        reason = result["unresolved"][0]["reason"]
        assert "missing_path" in reason, (
            f"Expected reason to contain 'missing_path'; got {reason!r}"
        )

    def test_max_iters_none_reads_from_env(self, tmp_path: pathlib.Path) -> None:
        """max_iters=None must read SPECDEV_LLM_INNER_MAX_ITERS from the config.

        Regression test for Finding 5 (first review): the lazy config read path
        (lines 168-170 of loop_inner.py) was never exercised by tests.
        """
        from specdev_tools.core.config import reset_config

        spec_root, git_root = make_spec_root(tmp_path)
        prev = os.environ.pop("SPECDEV_LLM_INNER_MAX_ITERS", None)
        try:
            os.environ["SPECDEV_LLM_INNER_MAX_ITERS"] = "1"
            reset_config()
            # With max_iters=None, config drives max_iters=1 → exits after 1 iter.
            adapter = MockAdapter([_MISS_RESPONSE_1])
            result = run_inner_loop(
                task=_TASK,
                step_structure_summary=_STEP_SUMMARY,
                upstream_structure=_UPSTREAM,
                prompt_nn=_PROMPT_NN,
                adapter=adapter,
                spec_root=spec_root,
                git_root=git_root,
                max_iters=None,
            )
            assert result["iterations"] == 1
            assert result["ok"] is False
        finally:
            if prev is None:
                os.environ.pop("SPECDEV_LLM_INNER_MAX_ITERS", None)
            else:
                os.environ["SPECDEV_LLM_INNER_MAX_ITERS"] = prev
            reset_config()


# ---------------------------------------------------------------------------
# _format_nearest unit tests
# ---------------------------------------------------------------------------

class TestFormatNearest:
    """Direct tests for the _format_nearest helper."""

    def test_empty_list_returns_none_string(self) -> None:
        assert _format_nearest([]) == "(none)"

    def test_dict_nearest_extracts_id(self) -> None:
        misses = [{"pointer": {"file": "f.json", "id": "fr-x"}, "nearest": [{"id": "fr-y", "score": 0.9}]}]
        result = _format_nearest(misses)
        assert "fr-y" in result
        assert "fr-x" in result

    def test_string_nearest_included(self) -> None:
        misses = [{"pointer": {"file": "f.json", "id": "fr-x"}, "nearest": ["fr-alt"]}]
        result = _format_nearest(misses)
        assert "fr-alt" in result

    def test_no_nearest_shows_none(self) -> None:
        misses = [{"pointer": {"file": "f.json", "id": "fr-x"}, "nearest": []}]
        result = _format_nearest(misses)
        assert "none" in result.lower()

    def test_multiple_misses_all_present(self) -> None:
        misses = [
            {"pointer": {"file": "f.json", "id": "fr-a"}, "nearest": [{"id": "fr-a1", "score": 0.8}]},
            {"pointer": {"file": "f.json", "id": "fr-b"}, "nearest": [{"id": "fr-b1", "score": 0.7}]},
        ]
        result = _format_nearest(misses)
        assert "fr-a" in result
        assert "fr-b" in result
        assert "fr-a1" in result
        assert "fr-b1" in result
