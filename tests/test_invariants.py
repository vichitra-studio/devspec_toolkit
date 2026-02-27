"""Dedicated tests for the invariant engine (_tiny_eval + run_invariants)."""

from __future__ import annotations

import inspect
import json
import os

import pytest

from specdev_tools.validation.invariants import _tiny_eval, run_invariants


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_spec_file(tmp_path, rules, filename="06_invariants.json"):
    """Write a minimal step-06 invariant spec file into *tmp_path*."""
    spec = {
        "$schema": "https://specdev.local/schema/06_invariants.schema.json",
        "id": "invariants-test",
        "owner": "api",
        "created_at": "2025-01-01T00:00:00Z",
        "seed_refs": [],
        "spec_refs_ingested": [],
        "rules": rules,
        "generation_quality": {"assumptions": []},
        "canonical_refs_used": [],
        "canonical_proposals": [],
        "canonical_conflicts": [],
    }
    path = tmp_path / filename
    path.write_text(json.dumps(spec), encoding="utf-8")
    return path


def _single_rule(expression, language="jsonlogic", inv_id="inv-test"):
    """Return a single rule dict ready for inclusion in a rules array."""
    return {
        "inv_id": inv_id,
        "description": "test rule",
        "language": language,
        "expression": expression,
        "scope": {"components": ["test"], "apis": []},
        "severity": "error",
        "trace": [],
    }


# ===================================================================
# TestTinyEval — unit tests for _tiny_eval
# ===================================================================

class TestTinyEval:
    """Unit tests for the _tiny_eval JSONLogic evaluator."""

    # --- literal passthrough ---

    def test_literal_int(self):
        assert _tiny_eval(42, {}) == 42

    def test_literal_str(self):
        assert _tiny_eval("hello", {}) == "hello"

    def test_literal_bool_true(self):
        assert _tiny_eval(True, {}) is True

    def test_literal_bool_false(self):
        assert _tiny_eval(False, {}) is False

    def test_literal_none(self):
        assert _tiny_eval(None, {}) is None

    # --- var resolution ---

    def test_var_nested_path(self):
        ctx = {"user": {"name": "Ada"}}
        assert _tiny_eval({"var": "user.name"}, ctx) == "Ada"

    def test_var_missing_returns_none(self):
        assert _tiny_eval({"var": "missing.path"}, {}) is None

    # --- comparison operators ---

    @pytest.mark.parametrize("op, a, b, expected", [
        (">=", 5, 3, True),
        (">=", 3, 3, True),
        (">=", 2, 3, False),
        ("<=", 3, 5, True),
        ("<=", 3, 3, True),
        ("<=", 5, 3, False),
        (">", 5, 3, True),
        (">", 3, 3, False),
        ("<", 3, 5, True),
        ("<", 3, 3, False),
        ("==", 1, 1, True),
        ("==", 1, 2, False),
        ("!=", 1, 2, True),
        ("!=", 1, 1, False),
    ])
    def test_comparison_operators(self, op, a, b, expected):
        assert _tiny_eval({op: [a, b]}, {}) is expected

    # --- Bug 6 regression: comparison with None operand ---

    def test_bug6_comparison_with_none_returns_none(self):
        """When a comparison operand is None (e.g. unresolved var), return None
        instead of raising TypeError."""
        result = _tiny_eval({">=": [{"var": "missing"}, 5]}, {})
        assert result is None

    def test_bug6_comparison_none_right(self):
        result = _tiny_eval({"==": [1, {"var": "missing"}]}, {})
        assert result is None

    # --- logical operators ---

    def test_and_true(self):
        assert _tiny_eval({"and": [True, True]}, {}) is True

    def test_and_false(self):
        assert _tiny_eval({"and": [True, False]}, {}) is False

    def test_or_true(self):
        assert _tiny_eval({"or": [False, True]}, {}) is True

    def test_or_false(self):
        assert _tiny_eval({"or": [False, False]}, {}) is False

    def test_not_true(self):
        assert _tiny_eval({"not": [True]}, {}) is False

    def test_not_false(self):
        assert _tiny_eval({"not": [False]}, {}) is True

    # --- collection operators ---

    def test_in_list(self):
        assert _tiny_eval({"in": ["a", ["a", "b", "c"]]}, {}) is True

    def test_in_string(self):
        assert _tiny_eval({"in": ["lo", "hello"]}, {}) is True

    def test_in_missing(self):
        assert _tiny_eval({"in": ["x", ["a", "b"]]}, {}) is False

    def test_contains_list(self):
        assert _tiny_eval({"contains": [["a", "b"], "a"]}, {}) is True

    def test_contains_missing(self):
        assert _tiny_eval({"contains": [["a", "b"], "z"]}, {}) is False

    # --- Bug 5 regression: empty operator ---

    @pytest.mark.parametrize("val, expected", [
        (None, True),
        ("", True),
        ([], True),
        ({}, True),
        ("hello", False),
        ([1], False),
    ])
    def test_bug5_empty_operator(self, val, expected):
        assert _tiny_eval({"empty": [val]}, {}) is expected

    # --- Bug 1 regression: unknown operator ---

    def test_bug1_unknown_operator_returns_none(self):
        result = _tiny_eval({"nonexistent_op": [1, 2]}, {})
        assert result is None

    # --- list passthrough ---

    def test_list_passthrough(self):
        result = _tiny_eval([1, "two", True], {})
        assert result == [1, "two", True]

    # --- nested expression ---

    def test_nested_expression(self):
        """Compose multiple operators: (5 > 3) and (not false)."""
        expr = {"and": [
            {">": [5, 3]},
            {"not": [False]},
        ]}
        assert _tiny_eval(expr, {}) is True


# ===================================================================
# TestRunInvariants — integration tests for run_invariants
# ===================================================================

class TestRunInvariants:
    """Integration tests for the run_invariants function."""

    def test_rule_passes(self, tmp_path):
        _make_spec_file(tmp_path, [_single_rule({"==": [1, 1]})])
        results = run_invariants(str(tmp_path), {})
        assert len(results) == 1
        assert results[0]["evaluable"] is True
        assert results[0]["result"] is True

    def test_rule_fails(self, tmp_path):
        _make_spec_file(tmp_path, [_single_rule({"==": [1, 2]})])
        results = run_invariants(str(tmp_path), {})
        assert len(results) == 1
        assert results[0]["evaluable"] is True
        assert results[0]["result"] is False

    # --- Bug 4 regression: non-jsonlogic languages ---

    def test_bug4_cel_language_not_evaluable(self, tmp_path):
        rule = _single_rule("x == y", language="cel")
        _make_spec_file(tmp_path, [rule])
        results = run_invariants(str(tmp_path), {})
        assert len(results) == 1
        assert results[0]["evaluable"] is False

    def test_bug4_text_language_not_evaluable(self, tmp_path):
        rule = _single_rule("some human-readable rule", language="text")
        _make_spec_file(tmp_path, [rule])
        results = run_invariants(str(tmp_path), {})
        assert len(results) == 1
        assert results[0]["evaluable"] is False

    # --- Bug 3 regression: expression starting with [ ---

    def test_bug3_list_expression_parsed(self, tmp_path):
        """A JSON string starting with '[' should be parsed, not rejected."""
        expr = json.dumps([{"==": [1, 1]}])
        rule = _single_rule(expr)
        _make_spec_file(tmp_path, [rule])
        results = run_invariants(str(tmp_path), {})
        assert len(results) == 1
        # It parses to a list, which evaluates to a list (not bool) → not evaluable
        # The key point is no exception and no false positive rejection.

    # --- Bug 1+4 regression: unknown operator ---

    def test_bug1_bug4_unknown_operator_not_evaluable(self, tmp_path):
        _make_spec_file(tmp_path, [_single_rule({"bogus_op": [1, 2]})])
        results = run_invariants(str(tmp_path), {})
        assert len(results) == 1
        assert results[0]["evaluable"] is False

    # --- Bug 4 regression: evaluable key present ---

    def test_bug4_result_contains_evaluable_key(self, tmp_path):
        _make_spec_file(tmp_path, [_single_rule({"==": [1, 1]})])
        results = run_invariants(str(tmp_path), {})
        assert "evaluable" in results[0]

    # --- Bug 2 regression: no unsafe json.load(open(...)) ---

    def test_bug2_no_unsafe_json_load_open(self):
        """Source code must not contain the anti-pattern json.load(open(...)."""
        src = inspect.getsource(run_invariants)
        assert "json.load(open(" not in src

    # --- Real fixture test ---

    def test_real_fixture_valid_full(self):
        """Load the real step_06 fixtures directory and evaluate with sample data."""
        fixture_dir = os.path.join(
            os.path.dirname(__file__),
            "fixtures", "step_06",
        )
        assert os.path.isdir(fixture_dir), f"Fixture dir not found: {fixture_dir}"

        sample = {
            "headers": ["auth-token", "content-type"],
            "auth-token": "jwt-abc-123",
        }
        results = run_invariants(fixture_dir, sample)

        # Directory contains multiple spec files with rules across files
        assert len(results) >= 2, f"Expected at least 2 rules, got {len(results)}"

        # All jsonlogic auth rules should be evaluable and pass with our sample
        auth_rules = [r for r in results if r["inv_id"] == "invariant-user-authentication"]
        assert len(auth_rules) >= 1
        for r in auth_rules:
            assert r["evaluable"] is True
            assert r["result"] is True

        # cel rule should not be evaluable
        cel_rules = [r for r in results if r["inv_id"] == "invariant-data-consistency"]
        assert len(cel_rules) == 1
        assert cel_rules[0]["evaluable"] is False

    # --- Bug 6 regression (integration): missing var key ---

    def test_bug6_integration_missing_var_not_evaluable(self, tmp_path):
        """A rule referencing a var that does not exist in sample should be
        marked evaluable=False because _tiny_eval returns None (not a bool)."""
        expr = {">=": [{"var": "count"}, 10]}
        _make_spec_file(tmp_path, [_single_rule(expr)])
        results = run_invariants(str(tmp_path), {})
        assert len(results) == 1
        assert results[0]["evaluable"] is False
