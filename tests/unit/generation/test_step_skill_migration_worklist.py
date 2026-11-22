"""The skills and the migration worklist (WI-M10-13): the step skill reads it first, and who may run which ``align`` command."""
from __future__ import annotations

import json
import re
from pathlib import Path

from specdev_tools.migration.worklist import WORKLIST_FILE

ROOT = Path(__file__).parents[3]
SKILLS = ROOT / ".claude" / "skills"
STEP_SKILL = SKILLS / "specdev-step" / "SKILL.md"
CONTEXT_SKILL = SKILLS / "specdev-context" / "SKILL.md"
TRINITY_SKILL = SKILLS / "specdev-trinity" / "SKILL.md"
ALIGN_COMMAND = re.compile(r"`specdev (align [a-z-]+)")


def _flat(path: Path) -> str:
    return " ".join(path.read_text(encoding="utf-8").split())


def _paragraph() -> str:
    text = STEP_SKILL.read_text(encoding="utf-8")
    start = text.index("**Migration worklist:**")
    return " ".join(text[start : text.index("\n\n", start)].split())


def _cli_paths() -> set[str]:
    return {command["path"] for command in json.loads((ROOT / "tools" / "cli_commands.json").read_text(encoding="utf-8"))["commands"]}


def test_the_worklist_paragraph_exists_in_the_step_skill() -> None:
    text = STEP_SKILL.read_text(encoding="utf-8")
    assert text.index("### Step 1") < text.index("**Migration worklist:**") < text.index("**Pre-dispatch existence check:**")
    paragraph = _paragraph()
    assert f"spec/{WORKLIST_FILE}" in paragraph, "the paragraph names the file the migration writes"
    for said in ("align triage spec --step <NN>", "`audience: agent`", "`audience: operator`", "ask the operator", '--resolve <id> --note "'):
        assert said in paragraph, said


def test_every_align_command_the_paragraph_names_is_in_cli_commands_json() -> None:
    named = set(ALIGN_COMMAND.findall(_paragraph()))
    assert named == {"align triage"}
    assert named <= _cli_paths()


def test_the_context_skill_lists_triage_as_auto_invocable_and_apply_and_validate_as_confirm_before() -> None:
    text = _flat(CONTEXT_SKILL)
    auto = text[text.index("**Auto-invocable**") : text.index("**Human required**")]
    human = text[text.index("**Human required**") : text.index("## Error handling")]
    assert "`align triage`" in auto and "`align triage`" not in human
    for command in ("`align apply`", "`align validate`"):
        assert command in human and command not in auto, command
    assert {"align triage", "align apply", "align validate"} <= _cli_paths()


def test_the_trinity_skill_says_the_migration_writes_the_milestone_key() -> None:
    text = _flat(TRINITY_SKILL)
    assert "`specdev align` does not write it" not in text
    assert "the migration writes the key (`specdev align apply spec --auto`" in text
