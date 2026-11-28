"""Support for the tests of the trinity contracts in the agents, the prompts and the skill."""
from __future__ import annotations

import json
import re
from pathlib import Path


def _flags(text: str, command: str) -> set[str]:
    """The ``--flag`` tokens of every command ``specdev <command> ...`` the text gives: an inline code span or a line of a code block (a backslash continues the line)."""
    spans = re.findall(r"`(specdev [^`]*)`", text)
    lines = text.splitlines()
    for number, line in enumerate(lines):
        if line.lstrip().startswith("specdev "):
            chunk = line.strip()
            while chunk.endswith("\\") and number + 1 < len(lines):
                number += 1
                chunk = chunk[:-1] + " " + lines[number].strip()
            spans.append(chunk)
    out: set[str] = set()
    for span in spans:
        if span.startswith(f"specdev {command}"):
            out |= set(re.findall(r"(?<![\w-])(--[a-z][a-z-]*)", span))
    return out


def _item_with_findings(host: Path, name: str, document: dict) -> str:
    folder = host / ".specdev" / "findings"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / name
    path.write_text(json.dumps(document), encoding="utf-8")
    return str(path)
