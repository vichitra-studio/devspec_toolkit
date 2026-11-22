"""The list of commands a user can type after ``specdev``: the one reader of ``tools/cli_commands.json``.

``specdev registry-generate`` writes the file; a step-10 rule that names a command in ``cli_command`` is checked against it
(by the step-10 validator, and by the proof, which counts a rule as built when its command is on the list).
"""
from __future__ import annotations

import json
import os

CLI_COMMANDS_PATH = os.path.join("tools", "cli_commands.json")


def known_cli_commands(toolkit_root: str) -> frozenset[str]:
    """The command paths (``spec-check``, ``third-party pin``) listed by *toolkit_root*.

    Raises:
        OSError: the file cannot be read.  ValueError, KeyError: it is not the file ``registry-generate`` writes.
    """
    with open(os.path.join(toolkit_root, CLI_COMMANDS_PATH), encoding="utf-8") as handle:
        return frozenset(entry["path"] for entry in json.load(handle)["commands"])
