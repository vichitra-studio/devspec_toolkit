"""Tests for step_10 deep validation: owner values and commit message rules."""
import pytest
from specdev_tools.validation.validators.step_10 import validate_step_10


def _render(errors):
    """Render SpecError list to strings for assertion convenience."""
    return [e.render() for e in errors]


@pytest.fixture
def toolkit_root(tmp_path):
    return str(tmp_path)


class TestValidMinimal:
    def test_empty_instance(self, toolkit_root):
        errors = validate_step_10({}, toolkit_root)
        assert errors == []

    def test_valid_full(self, toolkit_root):
        instance = {
            "owner": "engineering",
            "commit_message_rules": {
                "pattern": r"^(feat|fix|docs)\(.+\):.+$",
                "allowed_types": ["feat", "fix", "docs"],
            },
        }
        errors = validate_step_10(instance, toolkit_root)
        assert errors == []


class TestOwnerValidation:
    def test_invalid_owner(self, toolkit_root):
        instance = {"owner": "invalid-owner"}
        errors = validate_step_10(instance, toolkit_root)
        rendered = _render(errors)
        assert any("Invalid owner" in e for e in rendered)

    def test_valid_owner(self, toolkit_root):
        instance = {"owner": "api"}
        errors = validate_step_10(instance, toolkit_root)
        rendered = _render(errors)
        assert not any("owner" in e.lower() for e in rendered)


class TestCommitPattern:
    def test_invalid_regex(self, toolkit_root):
        instance = {"commit_message_rules": {"pattern": "[invalid("}}
        errors = validate_step_10(instance, toolkit_root)
        rendered = _render(errors)
        assert any("Invalid regex" in e for e in rendered)

    def test_valid_regex(self, toolkit_root):
        instance = {"commit_message_rules": {"pattern": "^feat:.+"}}
        errors = validate_step_10(instance, toolkit_root)
        rendered = _render(errors)
        assert not any("regex" in e.lower() for e in rendered)


class TestWrongTypedValues:
    @pytest.mark.parametrize("owner", [["api"], {"a": 1}, 7])
    def test_wrong_typed_owner_does_not_raise(self, toolkit_root, owner):
        assert validate_step_10({"owner": owner}, toolkit_root) == []

    @pytest.mark.parametrize("commit_rules", [7, ["pattern"], "pattern", None])
    def test_wrong_typed_commit_message_rules_do_not_raise(self, toolkit_root, commit_rules):
        assert validate_step_10({"commit_message_rules": commit_rules}, toolkit_root) == []

    @pytest.mark.parametrize("pattern", [7, ["^feat"], {"p": 1}])
    def test_wrong_typed_pattern_does_not_raise(self, toolkit_root, pattern):
        assert validate_step_10({"commit_message_rules": {"pattern": pattern}}, toolkit_root) == []


class TestRemovedFieldsAreNotRead:
    def test_pr_rules_and_trace_are_ignored(self, toolkit_root):
        instance = {"pr_rules": ["nonexistent-rule"], "trace": [{"type": "completely-fake-type", "targets": ["INVALID"]}]}
        assert validate_step_10(instance, toolkit_root) == []
