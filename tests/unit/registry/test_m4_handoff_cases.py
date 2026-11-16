"""The M4 hand-off list: every E590 existence test the M3 step bundles deleted, kept as a resolver case."""
import json
from pathlib import Path

import pytest

TOOLKIT_ROOT = Path(__file__).resolve().parents[3]
HANDOFF_FILE = TOOLKIT_ROOT / "tests" / "fixtures" / "graph" / "m4_handoff_cases.json"
FIELDS = {"old_test", "old_input", "new_link_field", "expected"}


@pytest.fixture(scope="module")
def cases() -> list[dict]:
    return json.loads(HANDOFF_FILE.read_text(encoding="utf-8"))["cases"]


def test_handoff_file_entries_have_four_fields(cases):
    assert cases
    for case in cases:
        assert set(case) == FIELDS, case
        assert all(isinstance(case[name], str) and case[name].strip() for name in FIELDS), case


def test_each_old_test_is_recorded_once(cases):
    old_tests = [case["old_test"] for case in cases]
    assert len(old_tests) == len(set(old_tests))


def test_old_test_names_a_test_module_of_the_repo(cases):
    for case in cases:
        module = case["old_test"].split("::", 1)[0]
        assert (TOOLKIT_ROOT / module).is_file(), case["old_test"]
