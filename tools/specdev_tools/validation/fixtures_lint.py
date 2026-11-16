from __future__ import annotations
import json
from typing import Any

from ..core.errors import SpecError, make_error
from ..core.loaders import iter_spec_artifacts

_FIXTURES_SCHEMA_SUFFIX = "/08_fixtures.schema.json"


def _load_fixtures(spec_dir: str) -> list[Any]:
    """Return every fixture entry of every step 08 artifact under *spec_dir*; unreadable files are skipped."""
    fixtures: list[Any] = []
    for p in iter_spec_artifacts(spec_dir):
        try:
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(data, dict):
            continue
        schema = data.get("$schema", "")
        entries = data.get("fixtures", [])
        if isinstance(schema, str) and schema.endswith(_FIXTURES_SCHEMA_SUFFIX) and isinstance(entries, list):
            fixtures.extend(entries)
    return fixtures


def lint_fixtures(spec_dir: str) -> list[SpecError]:
    """Check the input / expected / status / header shape of every fixture under *spec_dir*.

    What a fixture verifies (``verifies`` / ``removes``) is the schema's concern and is not read here.
    Never raises on a wrong-typed fixture entry.
    """
    errors: list[SpecError] = []
    for fx in _load_fixtures(spec_dir):
        if not isinstance(fx, dict):
            continue
        fid = fx.get("fixture_id","<unknown>")
        expected = fx.get("expected")
        if "input" not in fx or expected is None:
            errors.append(make_error("E520", f"{fid}: missing input/expected"))
            continue
        if isinstance(expected, dict):
            mode = fx.get("mode")
            status = expected.get("status")
            if mode == "contract":
                if not isinstance(status, int) or status < 100 or status > 599:
                    errors.append(make_error("E520", f"{fid}: expected.status must be an HTTP status (100-599) for mode 'contract'"))
            body = expected.get("body")
            if body is not None and not isinstance(body, (dict, list, str, int, bool, float)):
                errors.append(make_error("E520", f"{fid}: expected.body must be JSON serializable"))
            headers = expected.get("headers")
            if headers is not None and not isinstance(headers, dict):
                errors.append(make_error("E520", f"{fid}: expected.headers must be an object"))
        else:
            # Add warning if mode is contract or api but expected is not a dictionary
            mode = fx.get("mode")
            if mode in ["contract", "api"]:
                errors.append(make_error("E520", f"{fid}: expected should be a dictionary for mode '{mode}' but got {type(expected).__name__}"))
    return errors
