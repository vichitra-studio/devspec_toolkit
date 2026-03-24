
from __future__ import annotations
import collections
import os, json, warnings

from ..core.errors import SpecError, make_error, render_errors
from ..core.trace_types import normalize_trace_type, is_valid_trace_type
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
                # Exclude evidence_ref - it's for evidence binding metadata, not spec traceability
                if k.endswith("_ref") and k != "evidence_ref" and isinstance(v, str):
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
    artifacts = {}
    for root, _, files in os.walk(spec_dir):
        for fn in files:
            if fn.endswith(".json"):
                p = os.path.join(root, fn)
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

def build_trace_matrix(repo_root: str, spec_dir: str) -> dict:
    # Reusing the existing matrix logic for 00-09 core steps for visualization purposes
    # Generalized Matrix visualization is much harder without a schema, so we keep 
    # the core matrix logic "Classic" for now but ensure it doesn't crash on extensions.
    # The crucial fix was validate_trace_integrity, which is now generic.
    
    # Collect step artifacts
    artifacts = {}
    for root, _, files in os.walk(spec_dir):
        for fn in files:
            if fn.endswith(".json"):
                p = os.path.join(root, fn)
                try:
                    data = load_json(p)
                    artifacts[data.get("id", p)] = data
                except (OSError, json.JSONDecodeError):
                    pass

    # Dynamic entity indexing: discover entities by _id fields + canon trace type validation
    entity_index = collections.defaultdict(list)  # normalized_trace_type -> [entity_objects]

    for data in artifacts.values():
        for key, value in data.items():
            if not isinstance(value, list):
                continue
            for item in value:
                if not isinstance(item, dict):
                    continue
                for field in item:
                    if not field.endswith("_id") or not isinstance(item[field], str):
                        continue
                    prefix = field[:-3]  # strip "_id"
                    normalized = normalize_trace_type(prefix)
                    if is_valid_trace_type(normalized):
                        entity_index[normalized].append(item)
                        break  # one entity type per object

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
        if "extension_generator" in schema or art_basename.startswith("ext_"):
            if "extensions" in data:
                extensions.extend(data.get("extensions", []))

    # Build links
    fr_to_api = collections.defaultdict(set)
    api_to_fixture = collections.defaultdict(set)
    api_to_nfr = collections.defaultdict(set)
    fr_to_nfr = collections.defaultdict(set)
    api_to_threat = collections.defaultdict(set)

    for fr in frs:
        for t in fr.get("trace", []):
            if t.get("type") == _MATRIX_LINK_API_TYPE:
                fr_to_api[fr["fr_id"]].add(t["id"])

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
