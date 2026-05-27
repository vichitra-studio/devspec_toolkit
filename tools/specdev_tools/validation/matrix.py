
from __future__ import annotations
import collections
import os, json, warnings

from ..core.errors import SpecError, make_error, render_errors
from ..core.loaders import iter_spec_artifacts
from ..core.trace_types import normalize_trace_type, is_valid_trace_type, get_trace_types
from ..core.entry_key_registry import list_entries, _ALWAYS_EXCLUDED
from .cross_artifact_checks import (
    collect_capability_ids,
    collect_glossary_term_ids,
    check_step_02_integrity,
    check_step_03_integrity,
    check_step_04_integrity,
)

# ---------------------------------------------------------------------------
# Sentinel & default constants for coverage threshold logic (BUG-2 fix)
# ---------------------------------------------------------------------------
_MISSING_FILE = object()  # sentinel: step_order.json absent or malformed
_DEFAULT_COVERAGE_THRESHOLDS = {"fr_coverage": 80, "mode": "warn"}

# ---------------------------------------------------------------------------
# Business-rule trace-type constants for matrix link building
# ---------------------------------------------------------------------------

# Business rule: the trace matrix connects FRs to APIs, APIs to fixtures and
# NFRs, and APIs to threats.  Only "api" and "fr" trace types carry meaning
# in these link-building loops.
# Rationale: the matrix is a *requirements-to-implementation* cross-reference.
# An FR traces to an API it exercises; an NFR may trace to an FR it
# constrains or an API it benchmarks; a fixture targets an API it tests; a
# threat targets an API it attacks.  Other trace types (doc, capability,
# component) are structural, not executable, so they do not appear in the
# matrix linkage.
_MATRIX_LINK_API_TYPE: str = "api"
_MATRIX_LINK_FR_TYPE: str = "fr"

_invalid_matrix_link_types = {
    t for t in (_MATRIX_LINK_API_TYPE, _MATRIX_LINK_FR_TYPE)
    if not is_valid_trace_type(t)
}
if _invalid_matrix_link_types:
    warnings.warn(
        f"matrix: link-building trace types contain unknown canon trace types: "
        f"{_invalid_matrix_link_types}",
        stacklevel=1,
    )

def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def collect_definitions_and_references(artifacts: dict) -> tuple[set[str], list[tuple[str, str]]]:
    """
    Generic traversal to find all ID definitions and references.
    
    Definition Heuristic:
    - Any field ending in '_id' (e.g., fr_id, api_id) is a definition.
    - Field 'id' is a definition UNLESS it appears in a reference list context.
    - Value must be a non-empty string.
    
    Reference Heuristic:
    - Lists named 'trace', 'targets', 'dependencies', 'deliverables', 'links', 'spec_refs' containing objects with 'id'
    - Fields ending in '_ref' or '_refs'
    """
    known_ids = set()
    references = [] # list of (source_file, target_id)

    # Contexts where 'id' is a REFERENCE, not a definition
    REFERENCE_CONTEXTS = {
        "trace", "targets", "deliverables", "links", "spec_refs", "ref", "refs"
    }

    def scan_obj(obj, source_file, path="", parent_key=None):
        if isinstance(obj, dict):
            # Check for definitions
            for k, v in obj.items():
                # 1. Standard definition pattern (*_id)
                if k.endswith("_id") and isinstance(v, str) and v:
                    known_ids.add(v)
                
                # 2. 'id' field is a definition unless parent is a reference list
                elif k == "id" and isinstance(v, str) and v:
                    # Check if parent key implies this is a reference container
                    if parent_key not in REFERENCE_CONTEXTS:
                        known_ids.add(v)
                
                # Check for explicit references (lists of objects with id)
                if k in REFERENCE_CONTEXTS and isinstance(v, list):
                    for item in v:
                        if isinstance(item, dict) and "id" in item:
                             references.append((source_file, item["id"]))
                
                # Check for direct references (field_ref: "target-id" or field_refs: ["id1", "id2"])
                # Exclude URI-shaped values (e.g. evidence_ref: "https://..." or "ci://...") —
                # those carry external-resource pointers, not spec IDs.
                if k.endswith("_ref") and isinstance(v, str) and "://" not in v:
                    references.append((source_file, v))
                elif k.endswith("_refs") and isinstance(v, list):
                    for ref_id in v:
                        if isinstance(ref_id, str):
                            references.append((source_file, ref_id))

                # Special case for Step 14 source_milestones (list of strings)
                if k == "source_milestones" and isinstance(v, list):
                    for ref_id in v:
                        if isinstance(ref_id, str):
                            references.append((source_file, ref_id))

            # Recurse
            for k, v in obj.items():
                # Pass 'k' as parent_key for the children
                scan_obj(v, source_file, path=f"{path}.{k}", parent_key=k)

        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                # Keep the same parent_key for items in a list (e.g. parent is "trace", items are trace objects)
                scan_obj(item, source_file, path=f"{path}[{i}]", parent_key=parent_key)

    for path, data in artifacts.items():
        scan_obj(data, path)
        
    return known_ids, references


def validate_trace_integrity(repo_root: str, spec_dir: str) -> list[SpecError]:
    """Check for broken trace references (Generic Implementation).

    The function loads all JSON artifacts from *spec_dir*, runs the generic
    broken-reference scan, then dispatches to per-step cross-artifact checks
    defined in :mod:`cross_artifact_checks`.
    """
    del repo_root  # accepted for API symmetry with build_trace_matrix
    artifacts = {}
    for p in iter_spec_artifacts(spec_dir):
        try:
            data = load_json(p)
            artifacts[p] = data
        except (OSError, json.JSONDecodeError):
            pass

    known_ids, references = collect_definitions_and_references(artifacts)

    # Generic broken-reference check
    errors: list[SpecError] = []
    for src, tgt in references:
        if tgt and tgt not in known_ids and not (
            tgt.startswith("external:") or
            tgt.startswith("file:") or
            tgt.startswith("refs/")
        ):
            errors.append(make_error(
                "E590",
                f"Broken Trace in {os.path.basename(src)}: Reference to '{tgt}' not found.",
            ))

    # Collect shared cross-step indexes
    capability_ids = collect_capability_ids(artifacts)
    glossary_term_ids = collect_glossary_term_ids(artifacts)

    # Dispatch to per-step cross-artifact checks
    errors.extend(check_step_02_integrity(artifacts, capability_ids))
    errors.extend(check_step_03_integrity(artifacts))
    errors.extend(check_step_04_integrity(artifacts, glossary_term_ids, capability_ids))

    return errors

def _legacy_scan_data(
    data: dict,
    entity_index: dict,
    seen_entities: set,
    is_valid_type=is_valid_trace_type,
    normalize_type=normalize_trace_type,
) -> None:
    """Legacy entity discovery: scan all top-level list values for ``*_id`` fields.

    Used as a fallback when the toolkit-side entry_key_registry.json is not
    present (e.g. unit-test temp dirs, bare host repos without the registry).
    Mutates *entity_index* and *seen_entities* in place.
    """
    for value in data.values():
        if not isinstance(value, list):
            continue
        for item in value:
            if not isinstance(item, dict):
                continue
            for field in item:
                if not field.endswith("_id") or not isinstance(item[field], str):
                    continue
                prefix = field[:-3]  # strip "_id"
                normalized = normalize_type(prefix)
                if is_valid_type(normalized):
                    entity_key = (normalized, item[field])
                    if entity_key not in seen_entities:
                        entity_index[normalized].append(item)
                        seen_entities.add(entity_key)
                    break  # one entity type per object


def _extract_array_items(data: dict, array_path: str) -> list:
    """Extract items from *data* at *array_path* (supports nested paths like `.foo[].bar`).

    *array_path* uses dot-notation with an optional ``[]`` segment for nested arrays,
    e.g. ``.milestones[].tasks``.  A leading dot is stripped.  ``[]`` signals
    "iterate all list items and collect the sub-array from each".

    Examples::

        .functional_requirements           → data["functional_requirements"]
        .milestones[].tasks                → [t for m in data["milestones"] for t in m.get("tasks", [])]

    Returns an empty list if any key is missing or the value is not a list.
    """
    path = array_path.lstrip(".")
    # Split on "[]." to separate the parent path from the nested key
    if "[]." in path:
        parent_key, _, nested_key = path.partition("[].")
        parent_items = data.get(parent_key, [])
        if not isinstance(parent_items, list):
            return []
        result = []
        for parent_item in parent_items:
            if isinstance(parent_item, dict):
                sub = parent_item.get(nested_key, [])
                if isinstance(sub, list):
                    result.extend(sub)
        return result
    # Simple top-level array
    items = data.get(path, [])
    return items if isinstance(items, list) else []


def build_trace_matrix(
    repo_root: str,
    spec_dir: str,
    project_canon_dir: str | None = None,
) -> dict:
    """Build the trace matrix from *spec_dir* using the toolkit at *repo_root*.

    Args:
        repo_root: Path to the devspec_toolkit root (used for registry + canon).
        spec_dir: Path to the host spec directory.
        project_canon_dir: Optional path to the project-tier canon directory
            (e.g. ``<host>/spec/canon``).  When provided, project-defined
            trace_type entries are merged into the valid-type set via
            ``get_trace_types()``, making them visible to the matrix builder.
            When ``None`` only toolkit-core trace types are consulted (the
            historical default, preserved for backward compatibility).
    """
    # Resolve project-tier trace types when a project canon dir is supplied.
    # The module-level is_valid_trace_type() still works for call sites that
    # don't have a project_canon_dir; this local pair is used within the matrix
    # builder where project types must be visible.
    _active_trace_types, _active_aliases = get_trace_types(project_canon_dir)

    def _is_valid_type(value: str) -> bool:
        normalized = (value or "").strip()
        if not normalized:
            return False
        resolved = _active_aliases.get(normalized, normalized)
        return resolved in _active_trace_types

    def _normalize_type(value: str) -> str:
        normalized = (value or "").strip()
        if not normalized:
            return normalized
        return _active_aliases.get(normalized, normalized)

    # Classic step-00-to-09 link-building kept for visualization; extension artifacts
    # are indexed but not deeply linked.  FR→API direction: APIs carry the authoritative
    # FR trace (trace.type="fr"), not vice-versa — FRs trace to capabilities.

    # Determine whether the toolkit-side registry is available.  When repo_root
    # points to a temp directory (e.g. unit tests) the registry file won't exist
    # and we gracefully fall back to the legacy _id-suffix scan.
    _registry_available: bool
    try:
        list_entries("__probe__", repo_root)  # triggers FileNotFoundError if absent
        _registry_available = True
    except FileNotFoundError:
        _registry_available = False

    # Collect step artifacts (keyed by artifact id / path, preserving filesystem order)
    artifacts: dict[str, dict] = {}
    # Also keep the path→data mapping for registry-driven entity discovery
    path_to_data: dict[str, dict] = {}
    for p in iter_spec_artifacts(spec_dir):
        try:
            data = load_json(p)
            artifacts[data.get("id", p)] = data
            path_to_data[p] = data
        except (OSError, json.JSONDecodeError):
            pass

    # Entity indexing: registry-driven when the toolkit registry is available,
    # legacy _id-suffix scan when it is not (e.g. unit-test temp dirs).
    entity_index = collections.defaultdict(list)  # kind -> [entity_objects]
    seen_entities: set[tuple[str, str]] = set()   # (kind, id_value)

    if _registry_available:
        # W4-T1: Registry-driven entity discovery.
        # Iterate spec files in filesystem order (same order as legacy scan) so
        # that entity_index insertion order — and therefore matrix row order —
        # is stable and byte-equivalent to the pre-refactor output.
        for p, data in path_to_data.items():
            basename = os.path.basename(p)
            reg_entries = list_entries(basename, repo_root)
            if reg_entries is None:
                # Unknown file — fall back to legacy _id-suffix scan for this file only
                _legacy_scan_data(data, entity_index, seen_entities, _is_valid_type, _normalize_type)
                continue
            # reg_entries is a list (possibly empty) of RegistryEntry(array_path, id_field, kind)
            for reg_entry in reg_entries:
                # Skip corpus-excluded arrays (e.g. canonical_refs_used)
                array_key = reg_entry.array_path.lstrip(".").split("[")[0]
                if array_key in _ALWAYS_EXCLUDED:
                    continue
                items = _extract_array_items(data, reg_entry.array_path)
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    id_value = item.get(reg_entry.id_field)
                    if not id_value or not isinstance(id_value, str):
                        continue
                    entity_key = (reg_entry.kind, id_value)
                    if entity_key not in seen_entities:
                        entity_index[reg_entry.kind].append(item)
                        seen_entities.add(entity_key)
    else:
        # Legacy _id-suffix scan (fallback for unit tests and bare repo_roots
        # that do not have the toolkit registry installed).
        for data in artifacts.values():
            _legacy_scan_data(data, entity_index, seen_entities, _is_valid_type, _normalize_type)

    # Bridge to existing variable names (Sections C/D/E unchanged).
    # "fr" and "api" use the named constants; the remaining keys ("fixture",
    # "nfr", "threat") are dynamic entity-index lookups keyed by normalized
    # canon trace type and will be replaced when the matrix is fully dynamic.
    frs = entity_index.get(_MATRIX_LINK_FR_TYPE, [])
    apis = {a.get("api_id"): a for a in entity_index.get(_MATRIX_LINK_API_TYPE, []) if a.get("api_id")}
    fixtures = entity_index.get("fixture", [])
    nfrs = entity_index.get("nfr", [])
    threats = entity_index.get("threat", [])

    # Index extension files
    extensions = []
    for art_key, data in artifacts.items():
        schema = data.get("$schema", "")
        # Check if this artifact is an extension file
        art_basename = os.path.basename(art_key) if os.sep in art_key else art_key
        if "13-extension-manifest" in schema or art_basename.startswith("ext_"):
            if "extensions" in data:
                extensions.extend(data.get("extensions", []))

    # Build links
    fr_to_api = collections.defaultdict(set)
    api_to_fixture = collections.defaultdict(set)
    api_to_nfr = collections.defaultdict(set)
    fr_to_nfr = collections.defaultdict(set)
    api_to_threat = collections.defaultdict(set)

    # APIs carry the authoritative FR trace: each API lists the FRs it implements.
    # Iterating from the API side (rather than the FR side) is the correct direction:
    # FRs trace to capabilities, not to APIs.
    for api in apis.values():
        for t in api.get("trace", []):
            if t.get("type") == _MATRIX_LINK_FR_TYPE:
                fr_to_api[t["id"]].add(api["api_id"])

    for fx in fixtures:
        for t in fx.get("targets", []):
            if t.get("type") == _MATRIX_LINK_API_TYPE:
                api_to_fixture[t["id"]].add(fx["fixture_id"])

    for n in nfrs:
        for t in n.get("trace", []):
            if t.get("type") == _MATRIX_LINK_API_TYPE:
                api_to_nfr[t["id"]].add(n["nfr_id"])
            elif t.get("type") == _MATRIX_LINK_FR_TYPE:
                fr_to_nfr[t["id"]].add(n["nfr_id"])

    # Link Threats to APIs
    for th in threats:
        for t in th.get("target_ids", []):
            if t.get("type") == _MATRIX_LINK_API_TYPE:
                api_to_threat[t["id"]].add(th["threat_id"])

    # Emit matrix
    matrix = []
    for fr in frs:
        fr_id = fr["fr_id"]
        apirefs = sorted(fr_to_api.get(fr_id, []))
        
        # Collect NFRs from both direct FR traces and indirect API traces
        direct_nfrs = fr_to_nfr.get(fr_id, set())
        indirect_nfrs = {n for api in apirefs for n in api_to_nfr.get(api, set())}
        
        # Collect Threats via API links
        associated_threats = {th for api in apirefs for th in api_to_threat.get(api, set())}

        row = {
            "fr_id": fr_id,
            "apis": apirefs,
            "fixtures": sorted({fx for api in apirefs for fx in api_to_fixture.get(api, set())}),
            "nfrs": sorted(direct_nfrs | indirect_nfrs),
            "threats": sorted(associated_threats)
        }
        matrix.append(row)

    # Coverage summaries
    coverage = {
        "fr_total": len(frs),
        "fr_with_api": sum(1 for r in matrix if r["apis"]),
        "fr_with_fixture": sum(1 for r in matrix if r["fixtures"]),
        "fr_with_nfr": sum(1 for r in matrix if r["nfrs"]),
        "fr_with_threat": sum(1 for r in matrix if r["threats"]),
        "scaffolds_found": len([a for a in artifacts.values() if "15_scaffold" in a.get("$schema", "")]),
    }
    
    # Build milestone_coverage: map FR IDs -> sorted list of milestone IDs that reference them
    # Load from any Step 14 roadmap artifact found in the spec directory.
    milestone_coverage: dict[str, list[str]] = {}
    fr_to_milestones: dict[str, set[str]] = collections.defaultdict(set)
    for data in artifacts.values():
        schema = data.get("$schema", "")
        if "14-roadmap" in schema or "14_roadmap" in schema:
            for milestone in data.get("milestones", []):
                ms_id = milestone.get("milestone_id")
                if not ms_id:
                    continue
                # Collect fr_refs at milestone level
                for fr_ref in milestone.get("fr_refs", []):
                    fr_to_milestones[fr_ref].add(ms_id)
                # Collect fr_refs at task level
                for task in milestone.get("tasks", []):
                    for fr_ref in task.get("fr_refs", []):
                        fr_to_milestones[fr_ref].add(ms_id)
    if fr_to_milestones:
        milestone_coverage = {fr: sorted(ms_ids) for fr, ms_ids in sorted(fr_to_milestones.items())}

    # Add extensions to the result for traceability
    result = {"matrix": matrix, "coverage": coverage}

    # Add milestone_coverage if Step 14 data was found
    if milestone_coverage:
        result["milestone_coverage"] = milestone_coverage

    # Add extension information if available
    if extensions:
        result["extensions"] = extensions

    integrity_errors = validate_trace_integrity(repo_root, spec_dir)
    if integrity_errors:
        result["integrity_errors"] = render_errors(integrity_errors)

    # R9/T24: Configurable coverage threshold enforcement
    threshold_errors = _check_coverage_thresholds(coverage, repo_root)
    if threshold_errors:
        result.setdefault("integrity_errors", []).extend(render_errors(threshold_errors))

    return result


def _check_coverage_thresholds(coverage: dict, repo_root: str) -> list[SpecError]:
    """R9/T24: Enforce coverage thresholds from step_order.json."""
    errors: list[SpecError] = []
    config = _load_coverage_thresholds(repo_root)
    if config is _MISSING_FILE:
        # No step_order.json (or malformed) — graceful skip, no errors
        return errors
    if config is None:
        # File exists but coverage_thresholds key absent — apply defaults
        config = _DEFAULT_COVERAGE_THRESHOLDS

    assert isinstance(config, dict)
    mode = config.get("mode", "warn")
    fr_total = coverage.get("fr_total", 0)
    if fr_total == 0:
        return errors

    checks = [
        ("fr_coverage", coverage.get("fr_with_api", 0)),
    ]
    for check_name, actual_count in checks:
        threshold = config.get(check_name)
        if threshold is None:
            continue
        pct = (actual_count / fr_total) * 100
        if pct < threshold:
            code = "E592" if mode == "error" else "W592"
            semantic = "COVERAGE_THRESHOLD_BREACH" if mode == "error" else "COVERAGE_THRESHOLD_WARN"
            errors.append(make_error(
                code,
                f"{semantic} {check_name}={pct:.1f}% below threshold={threshold}%",
            ))
    return errors


def _load_coverage_thresholds(repo_root: str) -> dict | None | object:
    """Load coverage_thresholds from step_order.json.

    Returns:
        _MISSING_FILE  – file absent or malformed JSON (graceful skip).
        None           – file exists but ``coverage_thresholds`` key absent.
        dict           – the configured thresholds verbatim.
    """
    path = os.path.join(repo_root, "tools", "step_order.json")
    if not os.path.exists(path):
        return _MISSING_FILE
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("coverage_thresholds")
    except (OSError, json.JSONDecodeError):
        return _MISSING_FILE
