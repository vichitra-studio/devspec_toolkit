"""Tests for step_10 deep validation: commit patterns, trace types, link targets."""
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
            "pr_rules": ["validate", "test"],
            "trace": [{"type": "fr", "targets": ["fr-login"]}],
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


class TestTraceType:
    def test_invalid_trace_type(self, toolkit_root):
        instance = {"trace": [{"type": "completely-fake-type"}]}
        errors = validate_step_10(instance, toolkit_root)
        rendered = _render(errors)
        assert any("Invalid trace type" in e for e in rendered)


class TestLinkTarget:
    def test_valid_fr_target(self, toolkit_root):
        instance = {"trace": [{"type": "fr", "targets": ["fr-login"]}]}
        errors = validate_step_10(instance, toolkit_root)
        rendered = _render(errors)
        assert not any("invalid link target" in e.lower() for e in rendered)

    def test_valid_step_target(self, toolkit_root):
        instance = {"trace": [{"type": "fr", "targets": ["04"]}]}
        errors = validate_step_10(instance, toolkit_root)
        rendered = _render(errors)
        assert not any("invalid link target" in e.lower() for e in rendered)

    def test_invalid_target(self, toolkit_root):
        instance = {"trace": [{"type": "fr", "targets": ["INVALID"]}]}
        errors = validate_step_10(instance, toolkit_root)
        rendered = _render(errors)
        assert any("invalid link target" in e.lower() for e in rendered)


class TestPrRules:
    def test_invalid_pr_rule(self, toolkit_root):
        instance = {"pr_rules": ["validate", "nonexistent-rule"]}
        errors = validate_step_10(instance, toolkit_root)
        rendered = _render(errors)
        assert any("Invalid pr_rule" in e for e in rendered)
