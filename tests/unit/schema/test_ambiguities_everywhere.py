"""The open-ambiguity item is accepted, and the retired legacy item rejected, at all 20 `ambiguities` locations."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator

from specdev_tools.core.registry import get_shared_registry

_ROOT = Path(__file__).parents[3]
_SCHEMA_DIR = _ROOT / "schema"
_STEP_FILE_RE = re.compile(r"^(\d{2}a?)_")
_TRINITY_LOCATIONS = (
    ("16_anchor.schema.json", ("plan", "ambiguities")),
    ("16_impl_context.schema.json", ("plan", "ambiguities")),
    ("16_impl_context.schema.json", ("execution", "emergent_ambiguities")),
)
_OPEN_ITEM = {"id": "amb-session-timeout", "description": "The timeout is not stated.", "about": ["fr-user-login"]}
_LEGACY_ITEM = {"id": "amb-old", "description": "Old shape.", "severity": "high", "status": "tracking"}


def _step_locations() -> list[tuple[str, tuple[str, ...]]]:
    names = sorted(
        path.name
        for path in _SCHEMA_DIR.glob("*.schema.json")
        if (match := _STEP_FILE_RE.match(path.name)) and match.group(1) not in ("16",)
    )
    return [(name, ("ambiguities",)) for name in names]


_LOCATIONS = _step_locations() + list(_TRINITY_LOCATIONS)


def _errors_under(schema_file: str, path: tuple[str, ...], items: list[dict[str, Any]]) -> list[str]:
    """Validate `{path: items}` against the schema; return the messages of errors located at or below *path*."""
    schema = json.loads((_SCHEMA_DIR / schema_file).read_text())
    document: Any = items
    for name in reversed(path):
        document = {name: document}
    registry = get_shared_registry(str(_ROOT)).to_referencing_registry()
    validator = Draft202012Validator(schema, registry=registry)
    return [
        error.message
        for error in validator.iter_errors(document)
        if tuple(error.absolute_path)[: len(path)] == path
    ]


@pytest.mark.parametrize(("schema_file", "path"), _LOCATIONS, ids=lambda value: str(value))
def test_open_item_is_accepted(schema_file: str, path: tuple[str, ...]) -> None:
    assert _errors_under(schema_file, path, [_OPEN_ITEM]) == []


@pytest.mark.parametrize(("schema_file", "path"), _LOCATIONS, ids=lambda value: str(value))
def test_legacy_item_is_rejected(schema_file: str, path: tuple[str, ...]) -> None:
    assert _errors_under(schema_file, path, [_LEGACY_ITEM]) != []
