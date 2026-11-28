"""Tests for step_10 deep validation: commit message rules and rule commands."""
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
            },
        }
        errors = validate_step_10(instance, toolkit_root)
        assert errors == []


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


class TestRuleCommands:
    """The ``cli_command`` of a rule is checked against the command list ``registry-generate`` writes (``tools/cli_commands.json`` of the toolkit root)."""

    @pytest.fixture
    def listing(self, tmp_path):
        folder = tmp_path / "tools"
        folder.mkdir()
        (folder / "cli_commands.json").write_text(
            '{"commands": [{"path": "spec-check"}, {"path": "third-party check"}]}', encoding="utf-8"
        )
        return str(tmp_path)

    @staticmethod
    def _rules(*commands):
        return {"rules": [{"rule_id": f"rule-{index}", "cli_command": command} for index, command in enumerate(commands)]}

    def test_listed_commands_pass(self, listing):
        assert validate_step_10(self._rules("spec-check", "third-party check"), listing) == []

    def test_an_unknown_command_is_e530_naming_the_rule_and_the_command(self, listing):
        (error,) = validate_step_10(self._rules("spec-check", "no-such-command"), listing)
        assert error.code == "E530" and error.node_id == "rule-1"
        assert "'no-such-command'" in error.message and "'rule-1'" in error.message

    def test_a_rule_with_no_command_or_a_non_text_command_is_left_alone(self, listing):
        rules = {"rules": [{"rule_id": "rule-a", "enforcer": "review"}, {"rule_id": "rule-b", "cli_command": 3}, "text"]}
        assert validate_step_10(rules, listing) == []

    def test_an_unreadable_list_checks_nothing(self, tmp_path):
        assert validate_step_10(self._rules("no-such-command"), str(tmp_path)) == []
