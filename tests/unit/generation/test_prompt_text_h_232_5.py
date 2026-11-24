"""H-232-5: the step 03 prompt does not state as a rule what no tool checks."""
from __future__ import annotations

from pathlib import Path

_PROMPT = Path(__file__).resolve().parents[3] / "prompts" / "prompt_03_glossary.md"


def _drift_line() -> str:
    (line,) = [ln for ln in _PROMPT.read_text(encoding="utf-8").splitlines() if ln.startswith("- **Drift**")]
    return line


def test_prompt_03_drift_rule_names_what_is_unchecked():
    drift = _drift_line()
    assert "downstream steps MUST NOT introduce terms not defined here" not in drift
    assert "E741" in drift
