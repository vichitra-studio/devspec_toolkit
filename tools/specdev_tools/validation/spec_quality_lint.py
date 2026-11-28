from __future__ import annotations

import json
import os
import re
from typing import TYPE_CHECKING, Any

from ..core.errors import SpecError, make_error
from ..core.step_paths import is_extension_file
from .linter_utils import (
    build_lint_graph,
    collect_ids_and_refs,
    graph_covered_files,
    graph_known_ids,
    iter_json,
)

if TYPE_CHECKING:
    from ..graph.model import Graph


# Markers only. The English word "placeholder" is not a marker, and a marker written after a hyphen (the sentinel
# '-tbd', 'api-x-schema-tbd') is the sentinel the schemas and prompts tell authors to write. AUTO-DERIVE is the
# marker prompt 02 tells the author to resolve.
PLACEHOLDER_RE = re.compile(r"(?<![\w-])(TBD|TODO|FIXME|XXX|AUTO-DERIVE)\b", re.IGNORECASE)
STEP_ARTIFACT_RE = re.compile(r"^\d{2}[a-z]?_[a-z0-9_]+\.json$")
# Spec baseline: few|some|many|several|various — extended with safe additions: fast|reliable|easy|hard|quick
# R9: additional vague terms: appropriate|adequate|sufficient|reasonable|significant|typical|generally|usually
VAGUE_QUANTIFIER_RE = re.compile(
    r"\b(few|some|many|several|various|fast|reliable|easy|hard|quick"
    r"|appropriate|adequate|sufficient|reasonable|significant|typical|generally|usually)\b",
    re.IGNORECASE,
)
# Free-text fields to scan for vague language (beyond assumptions)
_VAGUE_SCAN_FIELDS = {
    "description", "statement", "rationale", "justification", "notes",
    "postconditions", "preconditions", "risks", "spikes",
    "migration_plan", "definition",
}
# Metadata fields that should NOT be scanned
_METADATA_FIELDS = {"$schema", "id", "owner", "created_at", "specdev_version"}
STEP_SCHEMA_URI_RE = re.compile(r"^vc:\d{2}[a-z]?-[a-z0-9-]+$")
CRITICAL_ARRAY_KEYS = {"functional_requirements", "terms", "apis", "rules", "nfrs", "fixtures", "milestones", "jobs", "threats"}

# Maximum number of assumptions before W572 fires.  Chosen empirically:
# most well-scoped spec artifacts have <10 assumptions.
_ASSUMPTION_THRESHOLD = 10


def lint_spec_quality(spec_dir: str, *, graph: Graph | None = None, spec_root: str | None = None) -> list[SpecError]:
    """Quality checks over every artifact of *spec_dir*, plus reference closure over the ids the spec defines.

    Definitions come from *graph* (built here when ``None``) for the files it covers and from a scan of the file
    for the others.  *spec_root* is the spec folder the caller was told (``--spec-root``; default: *spec_dir*, the
    folder it was handed): a file of its extensions folder is step 13's whatever its name, and no step artifact
    here.  Returns the findings; never raises.
    """
    errors: list[SpecError] = []
    spec_root = spec_root or spec_dir
    graph = build_lint_graph(spec_dir) if graph is None else graph
    covered = graph_covered_files(graph)
    known_ids = graph_known_ids(graph)
    refs: list[tuple[str, str, str]] = []

    for path in iter_json(spec_dir):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError) as exc:
            rel = os.path.relpath(path, spec_dir)
            errors.append(make_error("E520", f"UNRESOLVED_INPUT {rel} invalid_json {exc}"))
            continue
        if not _is_step_artifact(path, data, spec_root):
            continue
        rel = os.path.relpath(path, spec_dir)
        errors.extend(_check_required_top_level(rel, data))
        placeholder_errs, _ = _check_placeholders(rel, data)
        errors.extend(placeholder_errs)
        errors.extend(_check_critical_arrays(rel, data))
        errors.extend(_check_free_text_vague(rel, data))
        collect_ids_and_refs(data, rel, known_ids, refs, skip_ids_for_files=covered)

    # Second pass: assumption checks
    for path in iter_json(spec_dir):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue
        if not _is_step_artifact(path, data, spec_root):
            continue
        rel = os.path.relpath(path, spec_dir)
        errors.extend(_check_assumptions(rel, data))

    for rel, p, ref_id in refs:
        if ref_id.startswith("external:") or ref_id.startswith("cn:"):
            continue
        if ref_id not in known_ids:
            errors.append(make_error("E520", f"UNRESOLVED_INPUT {rel}:{p} ref={ref_id}"))

    return errors


def lint_spec_quality_file(path: str, spec_dir: str | None = None) -> list[SpecError]:
    """Run per-artifact quality checks used by single-file validation.

    This enforces deterministic top-level and placeholder/array checks without
    requiring full-directory reference closure.
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        rel = os.path.relpath(path, spec_dir or os.path.dirname(path) or ".")
        return [make_error("E520", f"UNRESOLVED_INPUT {rel} invalid_json {exc}")]

    if not _is_step_artifact(path, data):
        return []

    base = spec_dir or os.path.dirname(path) or "."
    rel = os.path.relpath(path, base)
    errs: list[SpecError] = []
    errs.extend(_check_required_top_level(rel, data))
    placeholder_errs, _ = _check_placeholders(rel, data)
    errs.extend(placeholder_errs)
    errs.extend(_check_critical_arrays(rel, data))
    errs.extend(_check_free_text_vague(rel, data))
    errs.extend(_check_assumptions(rel, data))
    return errs


def _check_assumptions(rel: str, data: Any, path: str = "") -> list[SpecError]:
    """Check each ``assumptions`` value: too many (W572), a marker (E512), a vague word (W571)."""
    errs: list[SpecError] = []
    if isinstance(data, dict):
        for k, v in data.items():
            p = f"{path}.{k}" if path else k
            if k == "assumptions":
                if isinstance(v, list) and len(v) > _ASSUMPTION_THRESHOLD:
                    errs.append(make_error("W572", f"ASSUMPTION_COUNT_HIGH {rel}:{p} count={len(v)}"))
                errs.extend(_scan_assumption_value(rel, v, p))
            else:
                errs.extend(_check_assumptions(rel, v, p))
    elif isinstance(data, list):
        for i, v in enumerate(data):
            errs.extend(_check_assumptions(rel, v, f"{path}[{i}]"))
    return errs


def _scan_assumption_value(rel: str, value: Any, path: str) -> list[SpecError]:
    """Scan one ``assumptions`` value: a string, a list of them, or an assumption node whose ``text`` is scanned."""
    errs: list[SpecError] = []
    if isinstance(value, dict):
        if "text" in value:
            errs.extend(_scan_assumption_value(rel, value["text"], f"{path}.text"))
    elif isinstance(value, str):
        if PLACEHOLDER_RE.search(value):
            errs.append(make_error("E512", f"ASSUMPTION_HAS_PLACEHOLDER {rel}:{path} value={value}"))
        for token in _scan_for_vague_language(value):
            errs.append(make_error("W571", f"ASSUMPTION_VAGUE_QUANTIFIER {rel}:{path} ref={token}"))
    elif isinstance(value, list):
        for i, item in enumerate(value):
            errs.extend(_scan_assumption_value(rel, item, f"{path}[{i}]"))
    return errs


def _scan_for_vague_language(text: str) -> list[str]:
    """Extract vague terms from a text string. Returns list of matched tokens."""
    return [m.group(1) for m in VAGUE_QUANTIFIER_RE.finditer(text)]


def _vague_findings(rel: str, path: str, text: str) -> list[SpecError]:
    """One W593 for each vague word of *text*, located at *path* of the file *rel*."""
    return [make_error("W593", f"VAGUE_LANGUAGE_FREE_TEXT {rel}:{path} ref={token}") for token in _scan_for_vague_language(text)]


def _check_scan_field_list(rel: str, items: list[Any], path: str) -> list[SpecError]:
    """W593 for each string of the list *items* of a scan field; an item that is not a string is walked."""
    errs: list[SpecError] = []
    for i, item in enumerate(items):
        if isinstance(item, str):
            errs.extend(_vague_findings(rel, f"{path}[{i}]", item))
        else:
            errs.extend(_check_free_text_vague(rel, item, f"{path}[{i}]"))
    return errs


def _check_free_text_vague(rel: str, data: Any, path: str = "") -> list[SpecError]:
    """R9/T18: Scan all free-text fields (not assumptions) for vague language."""
    errs: list[SpecError] = []
    if isinstance(data, dict):
        for k, v in data.items():
            if k in _METADATA_FIELDS:
                continue
            p = f"{path}.{k}" if path else k
            if k in _VAGUE_SCAN_FIELDS and isinstance(v, str):
                errs.extend(_vague_findings(rel, p, v))
            elif k in _VAGUE_SCAN_FIELDS and isinstance(v, list):
                errs.extend(_check_scan_field_list(rel, v, p))
            elif k != "assumptions":
                errs.extend(_check_free_text_vague(rel, v, p))
    elif isinstance(data, list):
        for i, v in enumerate(data):
            errs.extend(_check_free_text_vague(rel, v, f"{path}[{i}]"))
    return errs


def _check_required_top_level(rel: str, data: dict[str, Any]) -> list[SpecError]:
    errs: list[SpecError] = []
    for key in (
        "id",
        "owner",
        "created_at",
        "canonical_refs_used",
    ):
        if key not in data:
            errs.append(make_error("E520", f"UNRESOLVED_INPUT {rel} missing top-level '{key}'"))
    return errs


def _check_placeholders(rel: str, data: Any, path: str = "") -> tuple[list[SpecError], set[str]]:
    errs: list[SpecError] = []
    found: set[str] = set()
    if isinstance(data, dict):
        for k, v in data.items():
            p = f"{path}.{k}" if path else k
            child_errs, child_found = _check_placeholders(rel, v, p)
            errs.extend(child_errs)
            found.update(child_found)
    elif isinstance(data, list):
        for i, v in enumerate(data):
            p = f"{path}[{i}]"
            child_errs, child_found = _check_placeholders(rel, v, p)
            errs.extend(child_errs)
            found.update(child_found)
    elif isinstance(data, str):
        matches = PLACEHOLDER_RE.findall(data)
        if matches:
            found.update(m.upper() for m in matches)
            errs.append(make_error("E510", f"PLACEHOLDER_VALUE_FOUND {rel}:{path} value={data}"))
    return errs, found


def _check_critical_arrays(rel: str, data: dict[str, Any]) -> list[SpecError]:
    errs: list[SpecError] = []
    for key in CRITICAL_ARRAY_KEYS:
        if key in data and isinstance(data[key], list) and len(data[key]) == 0:
            errs.append(make_error("E520", f"UNRESOLVED_INPUT {rel} empty critical array '{key}'"))
    return errs


def _is_step_artifact(path: str, data: dict[str, Any] | None = None, spec_root: str | None = None) -> bool:
    """Whether *path* is a step artifact by its name or its ``$schema``; never a file of the extensions folder of *spec_root*."""
    if spec_root is not None and is_extension_file(path, spec_root):
        return False
    if STEP_ARTIFACT_RE.match(os.path.basename(path)):
        return True
    if isinstance(data, dict):
        schema_uri = data.get("$schema")
        if isinstance(schema_uri, str) and STEP_SCHEMA_URI_RE.match(schema_uri):
            return True
    return False
