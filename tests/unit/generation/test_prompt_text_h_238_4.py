"""H-238-4: the step_base description says ``$schema`` is required, and ``validate`` enforces it."""
from __future__ import annotations

import json
from pathlib import Path

from specdev_tools.validation.validate import validate_file

REPO_ROOT = Path(__file__).resolve().parents[3]


def test_step_base_describes_schema_uri_as_required() -> None:
    schema = json.loads((REPO_ROOT / "schema" / "core" / "step_base.schema.json").read_text(encoding="utf-8"))
    description = schema["properties"]["$schema"]["description"]
    assert "Required in every artifact" in description
    assert "missing_schema_uri" in description


def test_validate_reports_missing_schema_uri_for_a_file_without_it(tmp_path: Path) -> None:
    artifact = tmp_path / "00_charter.json"
    artifact.write_text(json.dumps({"id": "charter-v1"}), encoding="utf-8")

    errors = validate_file(str(REPO_ROOT), str(artifact))

    assert [(e.code, "missing_schema_uri" in e.message) for e in errors] == [("E520", True)]
