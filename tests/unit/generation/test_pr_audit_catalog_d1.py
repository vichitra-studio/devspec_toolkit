"""The PR audit's D1 catalog entry names the description-versus-Negative-Constraint case (DEVSPEC-213 ask 4)."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

_CATALOGS = Path(__file__).resolve().parents[3] / ".claude" / "skills" / "devspec_pr_audit" / "catalogs.md"
_D1_SECTION_RE = re.compile(r"^### D1 .*?(?=^### D2 )", re.DOTALL | re.MULTILINE)


@pytest.mark.skipif(not _CATALOGS.is_file(), reason=".claude is not present in this checkout")
def test_d1_names_the_description_vs_negative_constraint_case() -> None:
    match = _D1_SECTION_RE.search(_CATALOGS.read_text(encoding="utf-8"))
    assert match, "catalogs.md has no D1 section"
    assert "Negative Constraints" in match.group(0)
