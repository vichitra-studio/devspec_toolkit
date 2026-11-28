from __future__ import annotations
import json
from typing import Any

from ..core.errors import SpecError, make_error
from ..core.loaders import iter_spec_artifacts

_FIXTURES_SCHEMA_ID = "vc:08-fixtures"
_FIXTURES_SCHEMA_SUFFIX = "/08_fixtures.schema.json"
_CONTRACTS_SCHEMA_ID = "vc:05-interface-contracts"
_CONTRACTS_SCHEMA_SUFFIX = "/05_interface_contracts.schema.json"
_HTTP = "http"


def _is_step(data: Any, schema_id: str, suffix: str) -> bool:
    schema = data.get("$schema", "") if isinstance(data, dict) else ""
    return isinstance(schema, str) and (schema == schema_id or schema.endswith(suffix))


def _load_api_protocols(spec_dir: str) -> dict[str, str]:
    """The ``protocol`` of every API of every step 05 artifact under *spec_dir*, by ``api_id`` and by the ``error_id`` of each of its errors.

    An API that states no protocol counts as ``http``.  An unreadable file, or one whose ``apis`` is not a list, gives nothing.
    """
    protocols: dict[str, str] = {}
    for p in iter_spec_artifacts(spec_dir):
        try:
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue
        if not _is_step(data, _CONTRACTS_SCHEMA_ID, _CONTRACTS_SCHEMA_SUFFIX) or not isinstance(data.get("apis"), list):
            continue
        for api in data["apis"]:
            if not isinstance(api, dict):
                continue
            protocol = api.get("protocol") if isinstance(api.get("protocol"), str) else _HTTP
            errors = api.get("errors") if isinstance(api.get("errors"), list) else []
            for owner_id in (api.get("api_id"), *(error.get("error_id") for error in errors if isinstance(error, dict))):
                if isinstance(owner_id, str):
                    protocols[owner_id] = protocol
    return protocols


def _names_only_non_http_apis(fixture: dict[str, Any], protocols: dict[str, str]) -> bool:
    """True when *fixture* names at least one API (in ``verifies``, or through an API error in ``expects``) and none of them is an HTTP API."""
    named: list[str] = []
    for field in ("verifies", "expects"):
        ids = fixture.get(field)
        named.extend(protocols[i] for i in ids if isinstance(i, str) and i in protocols) if isinstance(ids, list) else None
    return bool(named) and _HTTP not in named


def _load_fixtures(spec_dir: str) -> list[Any]:
    """Return every fixture entry of every step 08 artifact under *spec_dir*; unreadable files are skipped.

    A step 08 artifact is recognised by the registry id ``vc:08-fixtures`` or by a ``$schema`` ending in
    ``/08_fixtures.schema.json`` (the only form 1.1.1 read).
    """
    fixtures: list[Any] = []
    for p in iter_spec_artifacts(spec_dir):
        try:
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(data, dict):
            continue
        entries = data.get("fixtures", [])
        if _is_step(data, _FIXTURES_SCHEMA_ID, _FIXTURES_SCHEMA_SUFFIX) and isinstance(entries, list):
            fixtures.extend(entries)
    return fixtures


def lint_fixtures(spec_dir: str) -> list[SpecError]:
    """Check the input / expected / status / header shape of every fixture under *spec_dir*.

    What a fixture verifies (``verifies`` / ``removes``) is the schema's concern; ``verifies`` and ``expects`` are read
    here only to learn the protocol of the APIs a ``contract`` fixture names (an API, or the API of an error it
    expects): its ``expected.status`` is an HTTP status (100 to 599) unless it names APIs and none of them is an HTTP
    API, when it is the status number of that protocol (an integer of 0 or more).  In a spec that has an API of
    another protocol, the HTTP finding says how such a fixture names its API.
    Never raises on a wrong-typed fixture entry.
    """
    errors: list[SpecError] = []
    protocols = _load_api_protocols(spec_dir)
    way_out = (
        "; a fixture of an API of another protocol names that API in verifies, or its error in expects, and gives that protocol's status number"
        if any(protocol != _HTTP for protocol in protocols.values()) else ""
    )
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
                is_integer = isinstance(status, int) and not isinstance(status, bool)
                if _names_only_non_http_apis(fx, protocols):
                    if not is_integer or status < 0:
                        errors.append(make_error(
                            "E520", f"{fid}: expected.status must be the status number of the API's protocol (an integer of 0 or more) for mode 'contract'",
                        ))
                elif not is_integer or status < 100 or status > 599:
                    errors.append(make_error("E520", f"{fid}: expected.status must be an HTTP status (100-599) for mode 'contract'{way_out}"))
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
