"""Tests for specdev_tools.core.json_output.format_errors_json and error_to_dict."""
from __future__ import annotations

import json

from specdev_tools.core.errors import SpecError
from specdev_tools.core.json_output import _make_remediation, error_to_dict, format_errors_json


class TestFormatErrorsJson:
    """Unit tests for the shared JSON output formatter."""

    def test_empty_errors_returns_pass(self) -> None:
        result = json.loads(format_errors_json([]))
        assert result["status"] == "PASS"
        assert result["error_count"] == 0
        assert result["warning_count"] == 0
        assert result["errors"] == []

    def test_only_warnings_returns_warn(self) -> None:
        errors = [
            SpecError(code="W571", message="vague quantifier found"),
            SpecError(code="W593", message="vague language in free text"),
        ]
        result = json.loads(format_errors_json(errors))
        assert result["status"] == "WARN"
        assert result["error_count"] == 0
        assert result["warning_count"] == 2
        assert len(result["errors"]) == 2
        assert all(e["severity"] == "warning" for e in result["errors"])

    def test_only_errors_returns_fail(self) -> None:
        errors = [
            SpecError(code="E510", message="placeholder found"),
        ]
        result = json.loads(format_errors_json(errors))
        assert result["status"] == "FAIL"
        assert result["error_count"] == 1
        assert result["warning_count"] == 0

    def test_mixed_errors_and_warnings_returns_fail(self) -> None:
        errors = [
            SpecError(code="E510", message="placeholder found"),
            SpecError(code="W571", message="vague quantifier"),
            SpecError(code="E520", message="unresolved input"),
        ]
        result = json.loads(format_errors_json(errors))
        assert result["status"] == "FAIL"
        assert result["error_count"] == 2
        assert result["warning_count"] == 1
        assert len(result["errors"]) == 3

    def test_context_dict_merging(self) -> None:
        result = json.loads(
            format_errors_json([], context={"command": "validate-all", "spec_dir": "/tmp/spec"})
        )
        assert result["command"] == "validate-all"
        assert result["spec_dir"] == "/tmp/spec"
        assert result["status"] == "PASS"

    def test_context_does_not_overwrite_core_fields(self) -> None:
        # context keys with same names as core fields will overwrite — this is
        # by design so callers can inject additional metadata, but core fields
        # should be set before context is merged.
        result = json.loads(
            format_errors_json(
                [SpecError(code="E510", message="placeholder")],
                context={"command": "test"},
            )
        )
        assert result["command"] == "test"
        # status should still reflect errors (set before context merge)
        assert result["status"] == "FAIL"

    def test_error_with_path_field(self) -> None:
        errors = [
            SpecError(code="E510", message="placeholder found", path="spec/04_frs.json"),
        ]
        result = json.loads(format_errors_json(errors))
        assert result["errors"][0]["path"] == "spec/04_frs.json"
        assert result["errors"][0]["code"] == "E510"
        assert result["errors"][0]["message"] == "placeholder found"
        assert result["errors"][0]["severity"] == "error"

    def test_error_without_path_omits_path_key(self) -> None:
        errors = [
            SpecError(code="E510", message="placeholder found"),
        ]
        result = json.loads(format_errors_json(errors))
        assert "path" not in result["errors"][0]

    def test_output_is_valid_json(self) -> None:
        errors = [
            SpecError(code="E510", message='has "quotes" and \\ backslashes'),
        ]
        raw = format_errors_json(errors)
        parsed = json.loads(raw)
        assert parsed["errors"][0]["message"] == 'has "quotes" and \\ backslashes'

    def test_severity_classification(self) -> None:
        errors = [
            SpecError(code="E510", message="err"),
            SpecError(code="W571", message="warn"),
        ]
        result = json.loads(format_errors_json(errors))
        assert result["errors"][0]["severity"] == "error"
        assert result["errors"][1]["severity"] == "warning"


class TestErrorToDict:
    """Unit tests for the error_to_dict helper."""

    def test_minimal_error_has_no_optional_fields(self) -> None:
        err = SpecError(code="E510", message="placeholder found")
        d = error_to_dict(err)
        assert d["code"] == "E510"
        assert d["message"] == "placeholder found"
        assert d["severity"] == "error"
        assert "path" not in d
        assert "subcode" not in d
        assert "file" not in d
        assert "jq_path" not in d
        assert "value" not in d

    def test_all_structured_fields_included_when_set(self) -> None:
        err = SpecError(
            code="E110",
            message="UNKNOWN_CANONICAL_ID cn:project:foo spec/01.json:entity_ref",
            subcode="UNKNOWN_CANONICAL_ID",
            file="spec/01_capabilities.json",
            jq_path=".entity_ref",
            value="cn:project:foo",
        )
        d = error_to_dict(err)
        assert d["subcode"] == "UNKNOWN_CANONICAL_ID"
        assert d["file"] == "spec/01_capabilities.json"
        assert d["jq_path"] == ".entity_ref"
        assert d["value"] == "cn:project:foo"

    def test_empty_string_value_is_included(self) -> None:
        err = SpecError(code="E530", message="test", value="")
        d = error_to_dict(err)
        assert "value" in d
        assert d["value"] == ""

    def test_none_value_omits_key(self) -> None:
        err = SpecError(code="E530", message="test", value=None)
        d = error_to_dict(err)
        assert "value" not in d

    def test_empty_string_subcode_is_included(self) -> None:
        err = SpecError(code="E530", message="test", subcode="")
        d = error_to_dict(err)
        assert "subcode" in d
        assert d["subcode"] == ""

    def test_empty_string_file_is_included(self) -> None:
        err = SpecError(code="E530", message="test", file="")
        d = error_to_dict(err)
        assert "file" in d
        assert d["file"] == ""

    def test_empty_string_jq_path_is_included(self) -> None:
        err = SpecError(code="E530", message="test", jq_path="")
        d = error_to_dict(err)
        assert "jq_path" in d
        assert d["jq_path"] == ""

    def test_structured_fields_appear_in_format_errors_json(self) -> None:
        err = SpecError(
            code="E530",
            message="INVENTED_ENUM_OR_ID spec/12.json:jobs[0].steps[0].command=frobulate",
            subcode="INVENTED_ENUM_OR_ID",
            file="spec/12_ci_gates.json",
            jq_path=".jobs[0].steps[0].command",
            value="frobulate",
        )
        result = json.loads(format_errors_json([err]))
        entry = result["errors"][0]
        assert entry["subcode"] == "INVENTED_ENUM_OR_ID"
        assert entry["file"] == "spec/12_ci_gates.json"
        assert entry["jq_path"] == ".jobs[0].steps[0].command"
        assert entry["value"] == "frobulate"


class TestMakeRemediation:
    """Unit tests for DEVSPEC-11 structured remediation blocks."""

    def test_e110_unknown_canonical_id_shape(self) -> None:
        err = SpecError(
            code="E110",
            message="UNKNOWN_CANONICAL_ID cn:project:foo spec/01.json:entity_ref",
            subcode="UNKNOWN_CANONICAL_ID",
            file="spec/01_capabilities.json",
            jq_path=".entity_ref",
            value="cn:project:foo",
        )
        r = _make_remediation(err)
        assert r is not None
        assert r["guide_code"] == "E110-UNKNOWN_CANONICAL_ID"
        assert r["parameters"]["fix_kind"] == "REGISTER_CANON_ENTRY"
        candidates = r["parameters"]["candidates"]
        assert len(candidates) >= 1
        assert candidates[0]["kind"] == "canon_accept"
        cmd = candidates[0]["command"]
        assert cmd.startswith("specdev canon-accept")
        # err.file must appear in the command, not a literal <spec-file> placeholder
        assert "spec/01_capabilities.json" in cmd
        assert "<spec-file>" not in cmd
        assert "cn:project:foo" in r["owner_story"]
        assert "references" in r["parameters"]

    def test_e110_remediation_falls_back_to_placeholder_when_file_is_none(self) -> None:
        err = SpecError(code="E110", message="test", subcode="UNKNOWN_CANONICAL_ID", value="cn:project:bar")
        r = _make_remediation(err)
        assert r is not None
        assert "<spec-file>" in r["parameters"]["candidates"][0]["command"]

    def test_e530_invented_enum_command_prefix_shape(self) -> None:
        err = SpecError(
            code="E530",
            message="INVENTED_ENUM_OR_ID spec/12.json:jobs[0].steps[0].command=frobulate",
            subcode="INVENTED_ENUM_OR_ID",
            file="spec/12_ci_gates.json",
            jq_path=".jobs[0].steps[0].command",
            value="frobulate",
        )
        r = _make_remediation(err)
        assert r is not None
        assert r["guide_code"] == "E530-INVENTED_ENUM_OR_ID"
        assert r["parameters"]["fix_kind"] == "ALLOWLIST_OR_REF"
        candidates = r["parameters"]["candidates"]
        assert len(candidates) == 2
        kinds = {c["kind"] for c in candidates}
        assert "extend_prefixes" in kinds
        assert "attach_command_ref" in kinds
        for c in candidates:
            assert c["command"].startswith("specdev ")
            assert "frobulate" in c["command"]
        # extend_prefixes must include --create-schema flag for first-use bootstrap (WS4)
        extend_cmd = next(c["command"] for c in candidates if c["kind"] == "extend_prefixes")
        assert "--create-schema vc:canon:command-prefixes" in extend_cmd
        assert "frobulate" in r["owner_story"]

    def test_e530_invented_enum_non_command_returns_none(self) -> None:
        # Stage/unit/pr_rules variants don't get remediation yet
        err = SpecError(
            code="E530",
            message="INVENTED_ENUM_OR_ID spec/12.json:jobs[0].stage=hyperspace",
            subcode="INVENTED_ENUM_OR_ID",
            file="spec/12_ci_gates.json",
            jq_path=".jobs[0].stage",
            value="hyperspace",
        )
        assert _make_remediation(err) is None

    def test_e530_linked_test_file_not_found_shape(self) -> None:
        err = SpecError(
            code="E530",
            message="LINKED_TEST_FILE_NOT_FOUND 09_impl_plan.json:linked_test_expectation path=tests/unit/missing.py",
            subcode="LINKED_TEST_FILE_NOT_FOUND",
            file="09_impl_plan.json",
            jq_path=".linked_test_expectation",
            value="tests/unit/missing.py",
        )
        r = _make_remediation(err)
        assert r is not None
        assert r["guide_code"] == "E530-LINKED_TEST_FILE_NOT_FOUND"
        assert r["parameters"]["fix_kind"] == "CREATE_OR_FIX_TEST_PATH"
        candidates = r["parameters"]["candidates"]
        assert len(candidates) >= 1
        assert candidates[0]["kind"] == "correct_path"
        cmd = candidates[0]["command"]
        assert cmd.startswith("specdev json patch")
        assert ".linked_test_expectation" in cmd
        # err.file must appear in the command, not a literal <spec-file> placeholder
        assert "09_impl_plan.json" in cmd
        assert "<spec-file>" not in cmd
        assert "tests/unit/missing.py" in r["owner_story"]

    def test_remediation_candidates_commands_start_with_specdev(self) -> None:
        errs = [
            SpecError(code="E110", message="test", subcode="UNKNOWN_CANONICAL_ID", value="cn:project:foo"),
            SpecError(code="E530", message="test", subcode="INVENTED_ENUM_OR_ID", jq_path=".jobs[0].steps[0].command", value="frobulate"),
            SpecError(code="E530", message="test", subcode="LINKED_TEST_FILE_NOT_FOUND", file="spec/09.json", jq_path=".linked_test_expectation", value="tests/missing.py"),
        ]
        for err in errs:
            r = _make_remediation(err)
            assert r is not None, f"expected remediation for {err.subcode}"
            for candidate in r["parameters"]["candidates"]:
                assert candidate["command"].startswith("specdev "), (
                    f"candidate command must start with 'specdev', got: {candidate['command']!r}"
                )

    def test_remediation_included_in_error_to_dict(self) -> None:
        err = SpecError(
            code="E530",
            message="test",
            subcode="INVENTED_ENUM_OR_ID",
            jq_path=".steps[0].command",
            value="frobnicate",
        )
        d = error_to_dict(err)
        assert "remediation" in d
        assert d["remediation"]["guide_code"] == "E530-INVENTED_ENUM_OR_ID"

    def test_no_remediation_for_unhandled_subcode(self) -> None:
        err = SpecError(code="E530", message="test", subcode="UNRESOLVED_NFR_REF", value="nfr-123")
        d = error_to_dict(err)
        assert "remediation" not in d
