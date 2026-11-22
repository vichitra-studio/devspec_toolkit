"""The code table of ``core/errors.py`` has no duplicate key, and the milestones' code bands do not overlap (WI-M10-01a).

A dict literal collapses a repeated key at run time, so a test on the loaded ``ERROR_CODES`` can never see one: this reads
the source with ``ast``.
"""

from __future__ import annotations

import ast
import re
from collections import Counter
from pathlib import Path

from specdev_tools.core.errors import ERROR_CODES

ERRORS_SOURCE = Path(__file__).resolve().parents[3] / "tools" / "specdev_tools" / "core" / "errors.py"

# Each milestone's numbers as (prefix, first, last).  M5's E882 (the baseline residue finding) lies inside the M10 block
# and belongs to M5; it is the one code a band holds that another milestone's numbers also span.
BANDS = {
    "M5": [("E", 760, 778)],
    "M8": [("E", 800, 849), ("W", 800, 849)],
    "M10": [("E", 880, 889)],
    "M9": [("E", 900, 929), ("W", 930, 939)],
}
OWNED_OUTSIDE_ITS_BAND = {"E882": "M5"}
M10_CODES = {"E880", "E881", "E884"}
CODE = re.compile(r"^([EW])(\d{3})$")


def _error_codes_dict() -> ast.Dict:
    tree = ast.parse(ERRORS_SOURCE.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        target = node.targets[0] if isinstance(node, ast.Assign) and len(node.targets) == 1 else getattr(node, "target", None)
        if isinstance(target, ast.Name) and target.id == "ERROR_CODES" and isinstance(getattr(node, "value", None), ast.Dict):
            return node.value
    raise AssertionError("ERROR_CODES is not a dict literal in core/errors.py")


def _band_of(code: str) -> list[str]:
    match = CODE.match(code)
    assert match, code
    prefix, number = match.group(1), int(match.group(2))
    return [name for name, ranges in BANDS.items() for p, low, high in ranges if p == prefix and low <= number <= high]


def test_error_codes_dict_has_no_duplicate_literal_keys():
    keys = [key.value for key in _error_codes_dict().keys if isinstance(key, ast.Constant)]
    assert len(keys) == len(_error_codes_dict().keys), "a key of ERROR_CODES is not a string literal"
    assert [key for key, count in Counter(keys).items() if count > 1] == []
    assert set(keys) == set(ERROR_CODES)


def test_milestone_code_bands_do_not_overlap():
    spans = [(name, p, low, high) for name, ranges in BANDS.items() for p, low, high in ranges]
    for index, (name, prefix, low, high) in enumerate(spans):
        for other, other_prefix, other_low, other_high in spans[index + 1 :]:
            assert prefix != other_prefix or high < other_low or other_high < low, f"{name} and {other} overlap"
    for code in sorted(ERROR_CODES):
        bands = _band_of(code)
        assert len(bands) <= 1, f"{code} is in the bands {bands}"
        if code in OWNED_OUTSIDE_ITS_BAND:
            assert bands == ["M10"] and OWNED_OUTSIDE_ITS_BAND[code] == "M5"
    registered_m10 = {code for code in ERROR_CODES if _band_of(code) == ["M10"]} - set(OWNED_OUTSIDE_ITS_BAND)
    assert registered_m10 == M10_CODES
