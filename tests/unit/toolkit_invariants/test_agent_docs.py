"""H-223-1 and H-223-2: the agent contract describes the agents that exist."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
AGENTS_MD = REPO_ROOT / "docs" / "agents" / "agents.md"
MANIFEST = REPO_ROOT / "docs" / "agents" / "manifest.json"
AGENT_FILES = REPO_ROOT / ".claude" / "agents"
SPECDEV_AGENTS = ("specdev-scope", "specdev-reviewer", "specdev-impl", "specdev-trinity-impl", "specdev-trinity-reviewer")


def _agents_md() -> str:
    return AGENTS_MD.read_text(encoding="utf-8")


def _manifest() -> dict:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def test_agents_md_describes_the_five_specdev_agents() -> None:
    section = _agents_md().split("## 9. The specdev agents and the review-fix loop", 1)[1]
    for name in SPECDEV_AGENTS:
        assert f"| `{name}` |" in section, name


def test_agents_md_has_no_two_retries_or_silent_autocorrect() -> None:
    text = _agents_md()
    assert "after two retries" not in text
    assert "auto‑correct silently" not in text and "auto-correct silently" not in text


def test_manifest_has_no_phase_triggers_and_agents_md_does_not_honour_them() -> None:
    assert "phase_triggers" not in _manifest()
    assert "phase_triggers" not in _agents_md()


def test_manifest_version_equals_first_changelog_version() -> None:
    manifest = _manifest()
    assert manifest["version"] == manifest["changelog"][0]["version"]


def test_clarify_contract_allows_the_blocker_json() -> None:
    contract = _manifest()["modes"]["clarify"]["output_contract"]
    assert contract["format"] == "markdown_bullets_or_blocker_json"
    assert any("blocker JSON" in restriction for restriction in contract["restrictions"])
    assert "blocker" in _agents_md().split("## 3.", 1)[1].split("## 4.", 1)[0]


@pytest.mark.skipif(not AGENT_FILES.is_dir(), reason=".claude/agents is absent (a host install without the links)")
def test_agents_md_names_every_specdev_agent_file() -> None:
    text = _agents_md()
    for path in sorted(AGENT_FILES.glob("specdev-*.md")):
        assert path.stem in text, path.stem
