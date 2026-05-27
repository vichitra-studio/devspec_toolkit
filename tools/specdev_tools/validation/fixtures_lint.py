
from __future__ import annotations
import os, json, warnings
from ..core.errors import SpecError, make_error
from ..core.loaders import iter_spec_artifacts
from ..core.trace_types import is_valid_trace_type, normalize_trace_type

# ---------------------------------------------------------------------------
# Business-rule trace-type sets for fixture target cross-referencing
# ---------------------------------------------------------------------------

# Business rule: fixtures validate concrete, testable artifacts.
# Each trace type listed here triggers a cross-reference check against the
# corresponding spec file (api -> 05, fr -> 04, invariant -> 06, nfr -> 07).
# Rationale: only these four artifact kinds have well-defined fixture
# semantics (input/expected pairs). Other trace types (doc, capability,
# component, threat) do not carry fixture-testable contracts.
_FIXTURE_CROSS_REF_TYPES: frozenset[str] = frozenset({"api", "fr", "invariant", "nfr"})

_invalid_fixture_types = {t for t in _FIXTURE_CROSS_REF_TYPES if not is_valid_trace_type(t)}
if _invalid_fixture_types:
    warnings.warn(
        f"fixtures_lint: _FIXTURE_CROSS_REF_TYPES contains unknown canon trace types: "
        f"{_invalid_fixture_types}",
        stacklevel=1,
    )


def lint_fixtures(spec_dir: str) -> list[SpecError]:
    errors: list[SpecError] = []
    apis = set()
    frs = set()
    invariants = set()
    nfrs = set()
    fixtures = []
    for p in iter_spec_artifacts(spec_dir):
        try:
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue
        s = data.get("$schema","")
        if s.endswith("/05_interface_contracts.schema.json"):
            for a in data.get("apis", []):
                if a.get("api_id"):
                    apis.add(a["api_id"])
        if s.endswith("/08_fixtures.schema.json"):
            fixtures.extend(data.get("fixtures", []))
        if s.endswith("/04_fr_list.schema.json"):
            for item in data.get("functional_requirements", []):
                if item.get("fr_id"): frs.add(item["fr_id"])
        if s.endswith("/06_invariants.schema.json"):
            for item in data.get("rules", []):
                if item.get("inv_id"): invariants.add(item["inv_id"])
        if s.endswith("/07_nfrs.schema.json"):
            for item in data.get("nfrs", []):
                if item.get("nfr_id"): nfrs.add(item["nfr_id"])

    for fx in fixtures:
        fid = fx.get("fixture_id","<unknown>")
        targets = fx.get("targets", [])
        if not targets:
            errors.append(make_error("E520", f"{fid}: missing targets"))
            continue
        # Map each cross-referenceable trace type to (id_pool, display_label).
        # Keys must stay in sync with _FIXTURE_CROSS_REF_TYPES (asserted below).
        _cross_ref_pools = {
            "api": (apis, "API"),
            "fr": (frs, "FR"),
            "invariant": (invariants, "Invariant"),
            "nfr": (nfrs, "NFR"),
        }
        assert set(_cross_ref_pools.keys()) == _FIXTURE_CROSS_REF_TYPES, (
            "cross_ref_pools keys must match _FIXTURE_CROSS_REF_TYPES"
        )
        for t in targets:
            # Check if target is a proper traceRef object before accessing its properties
            if isinstance(t, dict):
                tid = t.get("id", "")
                ttype = normalize_trace_type(t.get("type", ""))

                pool_entry = _cross_ref_pools.get(ttype)
                if pool_entry is not None:
                    pool, label = pool_entry
                    if tid not in pool:
                        errors.append(make_error("E590", f"{fid}: targets unknown {label} '{tid}'"))
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
