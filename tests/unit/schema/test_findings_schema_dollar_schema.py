"""``schema/infra/findings.schema.json`` declares ``$schema``, so the merged findings file passes a plain JSON Schema check too."""
from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator

from specdev_tools.validation.validate import validate_file

ROOT = Path(__file__).resolve().parents[3]
SCHEMA = json.loads((ROOT / "schema" / "infra" / "findings.schema.json").read_text(encoding="utf-8"))
DOCUMENT = {"$schema": "vc:infra:findings", "round": 1, "scope": "s", "generated_at": 1, "findings": []}


def _validate_file_messages(tmp_path: Path, document: dict) -> list[str]:
    path = tmp_path / "findings.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    return [error.message for error in validate_file(str(ROOT), str(path))]


def test_a_findings_document_with_dollar_schema_passes_a_plain_jsonschema_check() -> None:
    Draft202012Validator(SCHEMA).validate(DOCUMENT)


def test_the_same_document_passes_specdev_validate_and_without_dollar_schema_still_fails_it(tmp_path: Path) -> None:
    assert _validate_file_messages(tmp_path, DOCUMENT) == []
    without = {key: value for key, value in DOCUMENT.items() if key != "$schema"}
    assert _validate_file_messages(tmp_path, without), "a file without $schema is still refused (E520)"
