"""Tests for the CEL evaluator and invariants-check CLI failure path."""

from __future__ import annotations

import json
import os
import subprocess
import sys

from unittest.mock import patch

from specdev_tools.validation.invariants import _cel_eval, run_invariants
from ._helpers import make_spec_file as _make_spec_file  # pyright: ignore[reportMissingImports]


# ---------------------------------------------------------------------------
# Rule builder helpers (local — intentionally distinct from test_invariants.py's
# _single_rule because these defaults differ: CEL language, description param).
# ---------------------------------------------------------------------------

def _cel_rule(expression, inv_id="inv-cel-test", description="cel rule"):
    return {
        "inv_id": inv_id,
        "description": description,
        "language": "cel",
        "expression": expression,
        "scope": {"components": ["test"], "apis": []},
        "severity": "error",
        "trace": [],
    }


def _jsonlogic_rule(expression, inv_id="inv-jl-test"):
    return {
        "inv_id": inv_id,
        "description": "jsonlogic rule",
        "language": "jsonlogic",
        "expression": expression,
        "scope": {"components": ["test"], "apis": []},
        "severity": "error",
        "trace": [],
    }


# ===========================================================================
# _cel_eval unit tests
# ===========================================================================

class TestCelEval:

    # ---- core correctness ----

    def test_boolean_literal(self):
        raw, evaluable, reason = _cel_eval("1 == 1", {})
        assert evaluable is True
        assert reason is None
        assert bool(raw) is True

    def test_boolean_literal_false(self):
        raw, evaluable, reason = _cel_eval("1 == 2", {})
        assert evaluable is True
        assert reason is None
        assert bool(raw) is False

    def test_present_var(self):
        raw, evaluable, reason = _cel_eval(
            "post.status == 'published'", {"post": {"status": "published"}}
        )
        assert evaluable is True
        assert reason is None
        assert bool(raw) is True

    # ---- failure modes ----

    def test_missing_var_evaluates_to_false(self):
        # celpy 0.4.0: missing identifiers resolve to falsy defaults.
        raw, evaluable, reason = _cel_eval("post.status == 'x'", {})
        assert evaluable is True
        assert reason is None
        assert bool(raw) is False

    def test_function_on_missing_var_is_unevaluable(self):
        # size() on a missing variable triggers a real CELEvalError in 0.4.0.
        _, evaluable, reason = _cel_eval("size(post.items) > 0", {})
        assert evaluable is False
        assert reason == "cel_eval_error"

    def test_parse_error_returns_unevaluable_without_raising(self):
        _, evaluable, reason = _cel_eval("post.status ==", {})
        assert evaluable is False
        assert reason == "cel_parse_error"

    def test_empty_expression_returns_unevaluable(self):
        _, evaluable, reason = _cel_eval("", {})
        assert evaluable is False
        assert reason == "cel_parse_error"

    # ---- null / empty context ----

    def test_null_context_does_not_raise(self):
        # Passing ctx=None must not raise — treated as empty activation.
        result, evaluable, _ = _cel_eval("1 == 1", None)
        assert evaluable is True
        assert bool(result) is True

    def test_empty_context_does_not_raise(self):
        _, evaluable, _ = _cel_eval("true", {})
        assert evaluable is True

    # ---- operators and macros required by brief ----

    def test_ternary(self):
        raw, evaluable, _ = _cel_eval("x > 0 ? true : false", {"x": 5})
        assert evaluable is True
        assert bool(raw) is True

    def test_collection_macro_all(self):
        raw, evaluable, _ = _cel_eval("[1,2,3].all(n, n > 0)", {})
        assert evaluable is True
        assert bool(raw) is True

    def test_collection_macro_all_false(self):
        raw, evaluable, _ = _cel_eval("[1,2,3].all(n, n > 2)", {})
        assert evaluable is True
        assert bool(raw) is False

    def test_collection_macro_exists(self):
        raw, evaluable, _ = _cel_eval("[1,2,3].exists(n, n == 2)", {})
        assert evaluable is True
        assert bool(raw) is True

    def test_collection_macro_filter(self):
        # .filter returns a list; wrap in size() == N to get a boolean.
        raw, evaluable, _ = _cel_eval("size([1,2,3].filter(n, n > 1)) == 2", {})
        assert evaluable is True
        assert bool(raw) is True

    def test_string_contains(self):
        raw, evaluable, _ = _cel_eval("'abc'.contains('b')", {})
        assert evaluable is True
        assert bool(raw) is True

    def test_string_starts_with(self):
        raw, evaluable, _ = _cel_eval("'abc'.startsWith('a')", {})
        assert evaluable is True
        assert bool(raw) is True

    def test_string_matches(self):
        raw, evaluable, _ = _cel_eval("'abc'.matches('^a')", {})
        assert evaluable is True
        assert bool(raw) is True

    def test_size_function(self):
        raw, evaluable, _ = _cel_eval("size([1,2,3]) == 3", {})
        assert evaluable is True
        assert bool(raw) is True

    def test_has_macro(self):
        raw, evaluable, _ = _cel_eval("has(post.status)", {"post": {"status": "p"}})
        assert evaluable is True
        assert bool(raw) is True

    def test_non_boolean_result_is_reflected(self):
        # A non-boolean result from CEL is NOT the evaluator's job to reject —
        # that classification happens in run_invariants. _cel_eval itself returns
        # evaluable=True and the raw value for the caller to inspect.
        _, evaluable, reason = _cel_eval("1 + 2", {})
        assert evaluable is True   # parse + eval succeeded
        assert reason is None
        # raw is an IntType, not bool — caller (run_invariants) must detect this

    def test_hyphenated_context_key_silently_dropped(self):
        # Keys containing '-' are not valid CEL identifiers; _cel_eval must
        # silently skip them rather than raising.  Expressions not referencing
        # these keys must still evaluate successfully.
        raw, evaluable, reason = _cel_eval("1 == 1", {"auth-token": "jwt-abc"})
        assert evaluable is True
        assert reason is None
        assert bool(raw) is True

    def test_digit_prefixed_context_key_silently_dropped(self):
        # Keys starting with a digit are not valid CEL identifiers; the
        # `not k[:1].isdigit()` guard must silently skip them without raising.
        raw, evaluable, reason = _cel_eval("1 == 1", {"1abc": "value"})
        assert evaluable is True
        assert reason is None
        assert bool(raw) is True

    def test_cel_unavailable_returns_unevaluable(self):
        # When the celpy library is absent, _cel_eval must return
        # (None, False, "cel_unavailable") without raising.
        with patch("specdev_tools.validation.invariants._CEL_AVAILABLE", False):
            raw, evaluable, reason = _cel_eval("1 == 1", {})
        assert raw is None
        assert evaluable is False
        assert reason == "cel_unavailable"


# ===========================================================================
# run_invariants integration tests for CEL dispatch
# ===========================================================================

class TestRunInvariantsCel:

    def test_cel_pass(self, tmp_path):
        _make_spec_file(tmp_path, [_cel_rule("1 == 1")])
        res = run_invariants(str(tmp_path), {})
        assert len(res) == 1
        r = res[0]
        assert r["evaluable"] is True
        assert r["result"] is True
        assert r["language"] == "cel"
        assert "unevaluable_reason" not in r

    def test_cel_fail(self, tmp_path):
        _make_spec_file(tmp_path, [_cel_rule("1 == 2")])
        res = run_invariants(str(tmp_path), {})
        r = res[0]
        assert r["evaluable"] is True
        assert r["result"] is False

    def test_cel_missing_var_evaluates_to_false(self, tmp_path):
        # celpy 0.4.0: missing identifiers evaluate to falsy defaults.
        _make_spec_file(tmp_path, [_cel_rule("post.status == 'x'")])
        res = run_invariants(str(tmp_path), {})
        r = res[0]
        assert r["evaluable"] is True
        assert r["result"] is False

    def test_cel_function_on_missing_var_unevaluable(self, tmp_path):
        # size() on missing variable triggers real CELEvalError in 0.4.0.
        _make_spec_file(tmp_path, [_cel_rule("size(post.items) > 0")])
        res = run_invariants(str(tmp_path), {})
        r = res[0]
        assert r["evaluable"] is False
        assert r["unevaluable_reason"] == "cel_eval_error"

    def test_cel_parse_error_unevaluable(self, tmp_path):
        _make_spec_file(tmp_path, [_cel_rule("post.status ==")])
        res = run_invariants(str(tmp_path), {})
        r = res[0]
        assert r["evaluable"] is False
        assert r["unevaluable_reason"] == "cel_parse_error"

    def test_cel_non_boolean_result_unevaluable(self, tmp_path):
        # An expression that evaluates to a non-boolean (IntType) is marked
        # unevaluable — a CEL invariant must produce a boolean truth value.
        _make_spec_file(tmp_path, [_cel_rule("1 + 2")])
        res = run_invariants(str(tmp_path), {})
        r = res[0]
        assert r["evaluable"] is False
        assert r["unevaluable_reason"] == "non_boolean_result"

    def test_cel_null_expression_unevaluable(self, tmp_path):
        # expression=None in the spec — not a string, so CEL cannot compile it.
        rule = _cel_rule("placeholder")
        rule["expression"] = None
        _make_spec_file(tmp_path, [rule])
        res = run_invariants(str(tmp_path), {})
        r = res[0]
        assert r["evaluable"] is False
        assert r["unevaluable_reason"] == "cel_expression_not_string"

    def test_unsupported_language_unevaluable(self, tmp_path):
        rule = _cel_rule("anything")
        rule["language"] = "rego"
        _make_spec_file(tmp_path, [rule])
        res = run_invariants(str(tmp_path), {})
        r = res[0]
        assert r["evaluable"] is False
        assert r["unsupported_language"] == "rego"
        assert r["unevaluable_reason"] == "unsupported_language"

    def test_empty_rules_list(self, tmp_path):
        _make_spec_file(tmp_path, [])
        res = run_invariants(str(tmp_path), {})
        assert res == []

    def test_mixed_cel_and_jsonlogic(self, tmp_path):
        # Both languages in the same spec file are dispatched correctly.
        rules = [
            _cel_rule("1 == 1", inv_id="inv-cel"),
            _jsonlogic_rule({"==": [1, 1]}, inv_id="inv-jl"),
        ]
        _make_spec_file(tmp_path, rules)
        res = run_invariants(str(tmp_path), {})
        by_id = {r["inv_id"]: r for r in res}
        assert by_id["inv-cel"]["language"] == "cel"
        assert by_id["inv-cel"]["evaluable"] is True
        assert by_id["inv-jl"]["language"] == "jsonlogic"
        assert by_id["inv-jl"]["evaluable"] is True

    def test_language_field_always_present(self, tmp_path):
        # Every result record carries the language key regardless of evaluability.
        rules = [
            _cel_rule("post.missing == 1"),   # unevaluable
            _jsonlogic_rule({"==": [1, 1]}),  # evaluable
        ]
        _make_spec_file(tmp_path, rules)
        res = run_invariants(str(tmp_path), {})
        for r in res:
            assert "language" in r

    def test_jsonlogic_none_expression_is_not_evaluable(self, tmp_path):
        # A JSONLogic rule with expression=None resolves to None (not bool) →
        # marked evaluable=False, unevaluable_reason="unresolved_expression".
        rule = _jsonlogic_rule(None)  # type: ignore[arg-type]
        _make_spec_file(tmp_path, [rule])
        res = run_invariants(str(tmp_path), {})
        r = res[0]
        assert r["evaluable"] is False
        assert r["unevaluable_reason"] == "unresolved_expression"

    def test_walks_subdirectories(self, tmp_path):
        # run_invariants must recurse into sub-directories and collect rules
        # from all matching spec files found in the tree.
        sub = tmp_path / "sub"
        sub.mkdir()
        _make_spec_file(tmp_path, [_cel_rule("1 == 1", inv_id="inv-root")])
        _make_spec_file(sub, [_cel_rule("1 == 2", inv_id="inv-sub")])
        res = run_invariants(str(tmp_path), {})
        ids = {r["inv_id"] for r in res}
        assert "inv-root" in ids
        assert "inv-sub" in ids

    def test_skips_invalid_json_file(self, tmp_path):
        # A file with malformed JSON should be silently skipped, not crash.
        (tmp_path / "broken.json").write_text("{not valid json", encoding="utf-8")
        _make_spec_file(tmp_path, [_cel_rule("1 == 1")])
        res = run_invariants(str(tmp_path), {})
        # Only the valid spec contributes results.
        assert len(res) == 1

    def test_skips_non_invariant_schema_file(self, tmp_path):
        # A JSON file with a different $schema must be ignored.
        other = {"$schema": "vc:08-fixtures", "fixtures": []}
        (tmp_path / "other.json").write_text(json.dumps(other), encoding="utf-8")
        _make_spec_file(tmp_path, [_cel_rule("1 == 1")])
        res = run_invariants(str(tmp_path), {})
        assert len(res) == 1

    def test_empty_directory_returns_empty_list(self, tmp_path):
        # An empty spec directory must return [] — not raise or crash.
        res = run_invariants(str(tmp_path), {})
        assert res == []

    def test_cel_unavailable_propagated_to_result(self, tmp_path):
        # When celpy is absent, run_invariants must propagate the "cel_unavailable"
        # reason from _cel_eval into the result record — not swallow it.
        _make_spec_file(tmp_path, [_cel_rule("1 == 1")])
        with patch("specdev_tools.validation.invariants._CEL_AVAILABLE", False):
            res = run_invariants(str(tmp_path), {})
        assert len(res) == 1
        r = res[0]
        assert r["evaluable"] is False
        assert r["unevaluable_reason"] == "cel_unavailable"
        assert r["result"] is False

    def test_spec_file_missing_rules_key(self, tmp_path):
        # A valid schema file that omits the "rules" key should contribute 0
        # results — data.get("rules", []) must handle the missing key gracefully.
        spec = {
            "$schema": "vc:06-invariants",
            "id": "test",
            "owner": "api",
            "created_at": "2025-01-01T00:00:00Z",
        }
        (tmp_path / "06_invariants.json").write_text(json.dumps(spec), encoding="utf-8")
        res = run_invariants(str(tmp_path), {})
        assert res == []


# ===========================================================================
# CLI integration — exercise exit codes, envelopes, and output modes
# ===========================================================================

def _cli_run(tmp_path, rules, extra_args=(), sample=None, env_extra=None, json_output=True):
    spec_dir = tmp_path / "spec"
    spec_dir.mkdir(exist_ok=True)
    _make_spec_file(spec_dir, rules)
    sample_path = tmp_path / "sample.json"
    sample_path.write_text(json.dumps(sample or {}), encoding="utf-8")
    env = os.environ.copy()
    if env_extra:
        env.update(env_extra)
    cmd = [
        sys.executable,
        "-m",
        "specdev_tools.cli",
        "invariants-check",
        str(spec_dir),
        "--sample",
        str(sample_path),
    ]
    if json_output:
        cmd.append("--json")
    cmd.extend(extra_args)
    return subprocess.run(cmd, capture_output=True, text=True, env=env)


class TestCliInvariantsCheck:

    # ---- exit codes and envelope shape ----

    def test_all_pass_exits_zero(self, tmp_path):
        r = _cli_run(tmp_path, [_cel_rule("1 == 1")])
        assert r.returncode == 0, r.stderr
        env = json.loads(r.stdout)
        assert env["status"] == "PASS"
        assert env["error_count"] == 0
        assert env["warning_count"] == 0
        assert env["errors"] == []
        assert env["warnings"] == []

    def test_failing_rule_exits_nonzero(self, tmp_path):
        r = _cli_run(tmp_path, [_cel_rule("1 == 2")])
        assert r.returncode == 1
        env = json.loads(r.stdout)
        assert env["status"] == "FAIL"
        assert env["error_count"] == 1
        err = env["errors"][0]
        assert err["code"] == "E_INVARIANT_VIOLATION"
        assert err["inv_id"] == "inv-cel-test"
        assert "description" in err

    def test_unevaluable_is_warning_by_default(self, tmp_path):
        # size() on a missing variable triggers a real CELEvalError in celpy 0.4.0
        r = _cli_run(tmp_path, [_cel_rule("size(post.items) > 0")])
        assert r.returncode == 0
        env = json.loads(r.stdout)
        assert env["status"] == "PASS"
        assert env["error_count"] == 0
        assert env["warning_count"] == 1
        w = env["warnings"][0]
        assert w["code"] == "W_INVARIANT_UNEVALUABLE"
        assert w["reason"] == "cel_eval_error"

    def test_mixed_failed_and_unevaluable(self, tmp_path):
        # Both a failing rule and an unevaluable rule in the same run.
        rules = [
            _cel_rule("1 == 2", inv_id="inv-fail", description="failing"),
            _cel_rule("size(post.items) > 0", inv_id="inv-uneval", description="missing var size"),
        ]
        r = _cli_run(tmp_path, rules)
        assert r.returncode == 1
        env = json.loads(r.stdout)
        assert env["status"] == "FAIL"
        assert env["error_count"] == 1
        assert env["warning_count"] == 1
        assert env["errors"][0]["inv_id"] == "inv-fail"
        assert env["warnings"][0]["inv_id"] == "inv-uneval"

    # ---- strict mode ----

    def test_strict_flag_promotes_unevaluable_to_error(self, tmp_path):
        r = _cli_run(
            tmp_path, [_cel_rule("size(post.items) > 0")], extra_args=("--strict",)
        )
        assert r.returncode == 1
        env = json.loads(r.stdout)
        assert env["status"] == "FAIL"
        assert env["error_count"] == 1
        assert env["warning_count"] == 0
        err = env["errors"][0]
        assert err["code"] == "E_INVARIANT_UNEVALUABLE"
        assert "reason" in err

    def test_strict_env_var_value_1(self, tmp_path):
        r = _cli_run(
            tmp_path,
            [_cel_rule("size(post.items) > 0")],
            env_extra={"SPECDEV_INVARIANTS_STRICT": "1"},
        )
        assert r.returncode == 1
        assert json.loads(r.stdout)["status"] == "FAIL"

    def test_strict_env_var_value_true(self, tmp_path):
        r = _cli_run(
            tmp_path,
            [_cel_rule("size(post.items) > 0")],
            env_extra={"SPECDEV_INVARIANTS_STRICT": "true"},
        )
        assert r.returncode == 1
        assert json.loads(r.stdout)["status"] == "FAIL"

    def test_strict_env_var_value_yes(self, tmp_path):
        r = _cli_run(
            tmp_path,
            [_cel_rule("size(post.items) > 0")],
            env_extra={"SPECDEV_INVARIANTS_STRICT": "yes"},
        )
        assert r.returncode == 1
        assert json.loads(r.stdout)["status"] == "FAIL"

    def test_strict_does_not_affect_clean_run(self, tmp_path):
        r = _cli_run(
            tmp_path, [_cel_rule("1 == 1")], extra_args=("--strict",)
        )
        assert r.returncode == 0
        assert json.loads(r.stdout)["status"] == "PASS"

    def test_strict_env_var_falsy_does_not_promote(self, tmp_path):
        # Values other than "1"/"true"/"yes" must NOT enable strict mode.
        for falsy in ("0", "false", "no", "off", ""):
            r = _cli_run(
                tmp_path,
                [_cel_rule("size(post.items) > 0")],
                env_extra={"SPECDEV_INVARIANTS_STRICT": falsy},
            )
            env = json.loads(r.stdout)
            assert r.returncode == 0, f"SPECDEV_INVARIANTS_STRICT={falsy!r} should not trigger strict"
            assert env["status"] == "PASS", f"SPECDEV_INVARIANTS_STRICT={falsy!r} should not trigger strict"
            assert env["warning_count"] == 1

    # ---- human-readable output ----

    def test_human_readable_pass_exits_zero(self, tmp_path):
        r = _cli_run(tmp_path, [_cel_rule("1 == 1")], json_output=False)
        assert r.returncode == 0
        assert "1 rules" in r.stdout
        assert "0 failed" in r.stdout

    def test_human_readable_fail_exits_nonzero(self, tmp_path):
        r = _cli_run(tmp_path, [_cel_rule("1 == 2", description="broke")], json_output=False)
        assert r.returncode == 1
        assert "1 failed" in r.stdout
        assert "FAIL" in r.stdout
        assert "inv-cel-test" in r.stdout

    def test_human_readable_unevaluable_shows_warn(self, tmp_path):
        r = _cli_run(tmp_path, [_cel_rule("size(post.items) > 0")], json_output=False)
        assert r.returncode == 0
        assert "WARN" in r.stdout
        assert "inv-cel-test" in r.stdout

    def test_human_readable_strict_shows_error(self, tmp_path):
        r = _cli_run(
            tmp_path,
            [_cel_rule("size(post.items) > 0")],
            json_output=False,
            extra_args=("--strict",),
        )
        assert r.returncode == 1
        assert "ERROR" in r.stdout

    # ---- JSONLogic interop ----

    def test_jsonlogic_path_unaffected(self, tmp_path):
        r = _cli_run(tmp_path, [_jsonlogic_rule({"==": [1, 1]})])
        assert r.returncode == 0
        env = json.loads(r.stdout)
        assert env["status"] == "PASS"

    def test_jsonlogic_failing_rule(self, tmp_path):
        r = _cli_run(tmp_path, [_jsonlogic_rule({"==": [1, 2]})])
        assert r.returncode == 1
        assert json.loads(r.stdout)["status"] == "FAIL"

    # ---- envelope completeness ----

    def test_result_array_included_in_envelope(self, tmp_path):
        r = _cli_run(tmp_path, [_cel_rule("1 == 1")])
        env = json.loads(r.stdout)
        assert "result" in env
        assert isinstance(env["result"], list)
        assert len(env["result"]) == 1

    def test_warning_reason_matches_unevaluable_reason(self, tmp_path):
        r = _cli_run(tmp_path, [_cel_rule("post.status ==")])
        env = json.loads(r.stdout)
        w = env["warnings"][0]
        result_record = env["result"][0]
        assert w["reason"] == result_record["unevaluable_reason"]
