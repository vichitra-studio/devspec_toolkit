"""Support for the tests of the error-code and changelog catalogues: the documents they read and the way they read an entry."""
from __future__ import annotations

import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_ERROR_CODES_MD = _ROOT / "docs" / "developers" / "error-codes.md"
_REFERENCE_MD = _ROOT / "docs" / "developers" / "reference.md"
_SHARED_MD = _ROOT / "docs" / "prompts" / "shared_expectations.md"
_GOVERNANCE_MD = _ROOT / "docs" / "architecture" / "governance_architecture.md"
_CHANGELOG_MD = _ROOT / "changelog" / "v1.2.0.md"
_CHANGELOG_YAML = _ROOT / "changelog" / "v1.2.0.yaml"
_CLI_COMMANDS = _ROOT / "tools" / "cli_commands.json"


def _entry(text: str, code: str) -> str:
    """The body of the catalogue entry of *code* (from its heading to the next heading), or an empty string."""
    match = re.search(rf"^### {code}\b[^\n]*\n(.*?)(?=^#{{2,3}} )", text, re.S | re.M)
    return match.group(1) if match else ""


def _normalised(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("`", "").replace("**", "")).strip()


def _md_bullets(section: str) -> list[str]:
    md = _CHANGELOG_MD.read_text(encoding="utf-8")
    body = md.split(f"### {section}\n", 1)[1].split("\n### ", 1)[0]
    return [line[2:] for line in body.splitlines() if line.startswith("- ")]
