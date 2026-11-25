"""H-152-3: the fix-mode agent refreshes the canon with ``canon-accept --update``.

Reads ``.claude/agents/specdev-impl.md``.
"""
from __future__ import annotations

from pathlib import Path

import pytest

_IMPL = Path(__file__).resolve().parents[3] / ".claude" / "agents" / "specdev-impl.md"


@pytest.mark.skipif(not _IMPL.is_file(), reason=".claude is absent")
def test_the_fix_agent_names_the_canon_update_path():
    text = _IMPL.read_text(encoding="utf-8")
    assert "--namespace cn:project: --owner product --update" in text
    assert "run the command above with `--update` after the edit batch" in text
    assert "! changed (not updated, use --update)" in text
